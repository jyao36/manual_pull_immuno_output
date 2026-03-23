#!/usr/bin/env python3
"""
Repoint a Cromwell outputs.json template to a new workflow run on scratch.

Why this exists:
- The workflow-level outputs JSON used by pull_outputs.py is normally produced by querying
  Cromwell's API. If that step failed (e.g. scratch quota exceeded), you may still have all
  outputs under cromwell-executions/, but no outputs.json.

Approach:
- Use an existing outputs.json from a prior successful run as a *structural template*.
- Scan the new run's cromwell-executions workflow directory to index all files under
  call-*/**/execution/.
- For each path string in the template, derive a stable key: (call-chain, filename),
  where call-chain is the ordered list of "call-*" directory names in the path.
- Replace template paths with the corresponding real path from the new run.

This is designed for Cromwell directory structures where UUID segments differ run-to-run,
but the call directory names and final filenames are stable.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
FASTQC_ZIP_RE = re.compile(r"_(1|2)_fastqc\.zip$")


def is_uuid_segment(seg: str) -> bool:
    return bool(UUID_RE.match(seg))


def normalize_segment(seg: str) -> str:
    """
    Normalize segments that vary run-to-run but don't convey semantics.
    - Cromwell scatters/subworkflows introduce UUID path segments.
    - Cromwell "glob" output directories often include a content hash.
    """
    if is_uuid_segment(seg):
        return "{uuid}"
    return seg


def normalize_filename_sample_prefix(
    filename: str,
    *,
    sample_id: Optional[str],
) -> str:
    """
    Optionally normalize a leading sample-id prefix in filenames.
    Example:
      Hu_159_TUMOR_DNA.x.y -> {sample}_TUMOR_DNA.x.y
    """
    if not sample_id:
        return filename
    prefix = f"{sample_id}_"
    if filename.startswith(prefix):
        return "{sample}_" + filename[len(prefix) :]
    return filename


def normalize_relpath_parts(
    parts: Tuple[str, ...],
    *,
    filename_sample_id: Optional[str],
) -> Tuple[str, ...]:
    if not parts:
        return parts
    normalized = [
        normalize_segment(
            s
        )
        for s in parts
    ]
    normalized[-1] = normalize_filename_sample_prefix(
        normalized[-1],
        sample_id=filename_sample_id,
    )
    return tuple(normalized)


def normalized_relpath_key(
    workflow_dir: Path,
    file_path: Path,
    *,
    filename_sample_id: Optional[str],
) -> Tuple[str, ...]:
    """
    Key a file by its relative path from workflow_dir, but normalize unstable segments
    (UUIDs, glob hashes). This is usually stable across runs of the same workflow.
    """
    rel = file_path.relative_to(workflow_dir)
    return normalize_relpath_parts(
        rel.parts,
        filename_sample_id=filename_sample_id,
    )


def iter_execution_files(workflow_dir: Path) -> Iterable[Path]:
    """
    Yield all files under any execution directory in a workflow dir:
      <workflow_dir>/call-*/.../execution/<files...>
    """
    if not workflow_dir.is_dir():
        raise FileNotFoundError(f"workflow_dir does not exist or is not a directory: {workflow_dir}")

    # Avoid an expensive full-tree walk by only following call-* dirs at top-level.
    for top in workflow_dir.iterdir():
        if top.is_dir() and top.name.startswith("call-"):
            for root, _dirs, files in os.walk(top):
                root_p = Path(root)
                # Include files anywhere under an execution directory (execution/ and its subdirs).
                if "execution" not in root_p.parts:
                    continue
                for fn in files:
                    yield root_p / fn


OutputKey = Tuple[str, ...]  # normalized relative path parts (includes filename)
FastqcParentKey = Tuple[str, ...]


def key_for_output_path(
    path_str: str,
    *,
    filename_sample_id: Optional[str],
) -> Optional[OutputKey]:
    """
    Turn an outputs.json path string into a stable key.
    Returns None if it doesn't look like a local cromwell-executions path.
    """
    if not isinstance(path_str, str):
        return None
    p = Path(path_str)
    if p.name in ("", ".", "/"):
        return None
    parts = p.parts
    # Find ".../cromwell-executions/<wfName>/<uuid>/..." and key from there.
    for i, seg in enumerate(parts):
        if seg == "cromwell-executions" and i + 2 < len(parts):
            wf_id = parts[i + 2]
            if is_uuid_segment(wf_id):
                rel_parts = parts[i + 3 :]  # under workflow dir
                if not rel_parts:
                    return None
                return normalize_relpath_parts(
                    rel_parts,
                    filename_sample_id=filename_sample_id,
                )
    return None


def build_index(
    workflow_dir: Path,
    *,
    filename_sample_id: Optional[str],
) -> Dict[OutputKey, Path]:
    """
    Build a mapping from (call-chain, filename) -> actual file path in new workflow run.
    """
    idx: Dict[OutputKey, Path] = {}
    collisions: Dict[OutputKey, List[Path]] = {}

    for fp in iter_execution_files(workflow_dir):
        k = normalized_relpath_key(
            workflow_dir,
            fp,
            filename_sample_id=filename_sample_id,
        )
        if k in idx:
            collisions.setdefault(k, [idx[k]]).append(fp)
            continue
        idx[k] = fp

    if collisions:
        # Keep first-seen deterministically (os.walk is deterministic per-directory but not guaranteed overall).
        # Still, we want to warn because ambiguous mappings can cause wrong downloads.
        sys.stderr.write("WARNING: ambiguous output mappings detected for the following keys:\n")
        for k, fps in list(collisions.items())[:50]:
            sys.stderr.write(f"  - {k}  ({len(fps)} matches)\n")
        if len(collisions) > 50:
            sys.stderr.write(f"  ... and {len(collisions) - 50} more\n")

    return idx


def fastqc_read_mate(filename: str) -> Optional[str]:
    """
    Return read mate number ("1" or "2") for fastqc zip files.
    Example: SRR123_1_fastqc.zip -> "1"
    """
    m = FASTQC_ZIP_RE.search(filename)
    if not m:
        return None
    return m.group(1)


def normalize_parent_for_fastqc(parts: Tuple[str, ...]) -> FastqcParentKey:
    """
    Normalize parent path for fastqc fallback matching:
    - Keep existing UUID normalization
    - Collapse glob-* dir names so old/new run glob hashes can still match
    """
    out: List[str] = []
    for seg in parts:
        if seg.startswith("glob-"):
            out.append("{glob}")
        else:
            out.append(seg)
    return tuple(out)


def build_fastqc_index(idx: Dict[OutputKey, Path]) -> Dict[Tuple[FastqcParentKey, str], Path]:
    """
    Build fallback index for fastqc zips keyed by:
      (normalized-parent-through-glob, mate_number)
    """
    fastqc_idx: Dict[Tuple[FastqcParentKey, str], Path] = {}
    collisions: Dict[Tuple[FastqcParentKey, str], List[Path]] = {}

    for k, fp in idx.items():
        mate = fastqc_read_mate(fp.name)
        if mate is None:
            continue
        parent_key = normalize_parent_for_fastqc(k[:-1])
        fk = (parent_key, mate)
        if fk in fastqc_idx:
            collisions.setdefault(fk, [fastqc_idx[fk]]).append(fp)
            continue
        fastqc_idx[fk] = fp

    if collisions:
        sys.stderr.write("WARNING: ambiguous fastqc fallback mappings detected:\n")
        for fk, fps in list(collisions.items())[:50]:
            sys.stderr.write(f"  - {fk}  ({len(fps)} matches)\n")
        if len(collisions) > 50:
            sys.stderr.write(f"  ... and {len(collisions) - 50} more\n")

    return fastqc_idx


def fallback_fastqc_match(
    output_key: OutputKey,
    original_path: str,
    fastqc_idx: Dict[Tuple[FastqcParentKey, str], Path],
) -> Optional[Path]:
    """
    For unmapped fastqc paths, match by parent path and mate number (_1/_2),
    ignoring SRR prefix and glob hash differences.
    """
    mate = fastqc_read_mate(Path(original_path).name)
    if mate is None:
        return None
    parent_key = normalize_parent_for_fastqc(output_key[:-1])
    return fastqc_idx.get((parent_key, mate))


def expand_paths_under_glob_dirs(paths: List[str]) -> List[str]:
    """
    Given a list of mapped file paths, identify parent glob-* directories and
    return all files under those directories (deduplicated, sorted).
    """
    glob_dirs: List[Path] = []
    for p_str in paths:
        p = Path(p_str)
        glob_dir = None
        for parent in [p.parent, *p.parents]:
            if parent.name.startswith("glob-"):
                glob_dir = parent
                break
        if glob_dir is not None and glob_dir.is_dir():
            glob_dirs.append(glob_dir)

    if not glob_dirs:
        return paths

    seen = set()
    expanded: List[str] = []
    for gd in sorted(set(glob_dirs), key=lambda x: str(x)):
        for root, _dirs, files in os.walk(gd):
            root_p = Path(root)
            for fn in sorted(files):
                fp = root_p / fn
                s = str(fp)
                if s in seen:
                    continue
                seen.add(s)
                expanded.append(s)
    return expanded


def expand_immuno_pvacseq_mhc_lists(outputs_obj: Dict[str, Any], stats: Dict[str, int]) -> None:
    """
    Special handling for immuno.pVACseq.{mhc_i,mhc_ii}:
    replace existing path lists with all files under the mapped glob-* dirs.
    """
    immuno = outputs_obj.get("immuno")
    if not isinstance(immuno, dict):
        return
    pvacseq = immuno.get("pVACseq")
    if not isinstance(pvacseq, dict):
        return

    for k in ("mhc_i", "mhc_ii"):
        v = pvacseq.get(k)
        if not isinstance(v, list):
            continue
        if not all(isinstance(x, str) for x in v):
            continue
        expanded = expand_paths_under_glob_dirs(v)
        if len(expanded) != len(v):
            pvacseq[k] = expanded
            stats["pvacseq_glob_list_expanded"] += 1


def rewrite_outputs_obj(
    obj: Any,
    idx: Dict[OutputKey, Path],
    fastqc_idx: Dict[Tuple[FastqcParentKey, str], Path],
    *,
    template_sample_id: Optional[str],
    strict: bool,
    stats: Dict[str, int],
) -> Any:
    """
    Recursively rewrite every string path value under obj using idx, preserving shape.
    """
    if obj is None:
        return None
    if isinstance(obj, list):
        return [
            rewrite_outputs_obj(
                v,
                idx,
                fastqc_idx,
                template_sample_id=template_sample_id,
                strict=strict,
                stats=stats,
            )
            for v in obj
        ]
    if isinstance(obj, dict):
        return {
            k: rewrite_outputs_obj(
                v,
                idx,
                fastqc_idx,
                template_sample_id=template_sample_id,
                strict=strict,
                stats=stats,
            )
            for k, v in obj.items()
        }
    if isinstance(obj, str):
        stats["paths_seen"] += 1

        k = key_for_output_path(
            obj,
            filename_sample_id=template_sample_id,
        )
        if k and k in idx:
            new_path = str(idx[k])
            stats["paths_rewritten"] += 1
            return new_path

        if k:
            fallback = fallback_fastqc_match(k, obj, fastqc_idx)
            if fallback is not None:
                stats["paths_rewritten"] += 1
                stats["paths_rewritten_fastqc_fallback"] += 1
                return str(fallback)

        stats["paths_unmapped"] += 1
        if strict and k is not None:
            raise KeyError(f"Could not map output path: {obj}")
        return obj

    # numbers, booleans, etc.
    return obj


def infer_old_workflow_dir_from_template(template: Any) -> Optional[str]:
    """
    Try to infer the old workflow directory prefix:
      .../cromwell-executions/<workflow-name>/<workflow-id>
    from any path string in the template.
    """

    def iter_strings(x: Any) -> Iterable[str]:
        if x is None:
            return
        if isinstance(x, str):
            yield x
        elif isinstance(x, list):
            for v in x:
                yield from iter_strings(v)
        elif isinstance(x, dict):
            for v in x.values():
                yield from iter_strings(v)

    for s in iter_strings(template):
        # Find ".../cromwell-executions/<wfName>/<uuid>/..."
        parts = Path(s).parts
        for i, seg in enumerate(parts):
            if seg == "cromwell-executions" and i + 2 < len(parts):
                wf_name = parts[i + 1]
                wf_id = parts[i + 2]
                if is_uuid_segment(wf_id):
                    prefix = Path(*parts[: i + 3])
                    # sanity: wf_name is usually non-empty
                    if wf_name:
                        return str(prefix)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Repoint outputs.json template paths to a new cromwell-executions workflow directory."
    )
    ap.add_argument(
        "--template",
        required=True,
        help="Path to an existing outputs.json (template) from a successful run.",
    )
    ap.add_argument(
        "--scratch-dir",
        required=True,
        help=(
            "Full path to workflow scratch directory, e.g. "
            "/scratch.../Hu_159_attempt2/cromwell-executions/immuno/<workflow-uuid>"
        ),
    )
    ap.add_argument(
        "--sample-id",
        required=True,
        help="New sample identifier used for output naming and filename matching, e.g. Hu_159_attempt2",
    )
    ap.add_argument(
        "--template-sample-id",
        default=None,
        help=(
            "Sample identifier used in template filenames (old run). "
            "If provided, filenames beginning with this prefix are normalized for matching."
        ),
    )
    ap.add_argument(
        "--out-dir",
        default=".",
        help="Directory where output JSON is written (default: current directory).",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any cromwell-executions output path cannot be mapped.",
    )
    args = ap.parse_args()

    template_path = Path(args.template)
    new_workflow_dir = Path(args.scratch_dir)
    out_path = Path(args.out_dir) / f"{args.sample_id}_outputs.json"

    with open(template_path) as f:
        template = json.load(f)

    if "outputs" not in template or not isinstance(template["outputs"], dict):
        raise ValueError("Template JSON must look like: {\"outputs\": {...}}")

    idx = build_index(
        new_workflow_dir,
        filename_sample_id=args.sample_id,
    )
    fastqc_idx = build_fastqc_index(idx)

    stats = {
        "paths_seen": 0,
        "paths_rewritten": 0,
        "paths_rewritten_fastqc_fallback": 0,
        "paths_unmapped": 0,
        "pvacseq_glob_list_expanded": 0,
    }

    rewritten = {
        "outputs": rewrite_outputs_obj(
            template["outputs"],
            idx,
            fastqc_idx,
            template_sample_id=args.template_sample_id,
            strict=args.strict,
            stats=stats,
        )
    }
    expand_immuno_pvacseq_mhc_lists(rewritten["outputs"], stats)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(rewritten, f, indent=4, sort_keys=True)
        f.write("\n")

    sys.stderr.write(
        "Done.\n"
        f"  template: {template_path}\n"
        f"  new_workflow_dir: {new_workflow_dir}\n"
        f"  wrote: {out_path}\n"
        f"  sample_id (new run): {args.sample_id}\n"
        f"  template_sample_id (old run): {args.template_sample_id}\n"
        f"  paths_seen: {stats['paths_seen']}\n"
        f"  paths_rewritten: {stats['paths_rewritten']}\n"
        f"  paths_rewritten_fastqc_fallback: {stats['paths_rewritten_fastqc_fallback']}\n"
        f"  pvacseq_glob_list_expanded: {stats['pvacseq_glob_list_expanded']}\n"
        f"  paths_unmapped (left as-is): {stats['paths_unmapped']}\n"
    )

    if args.strict and stats["paths_unmapped"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

