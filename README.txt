## Rebuild JSON Helper

### Purpose
- Some immuno runs fail at artifact pull with `OSError: [Errno 122] Disk quota exceeded` (on WashU RIS).
- Workflow outputs still exist in scratch under `cromwell-executions`, but standard metadata/outputs retrieval can fail after workflow shutdown.
- This is also intended to be used on Discovery where the immuno pipeline has been run but need to condense the outputs.
- This directory provides a manual recovery path:
  1) rebuild an `outputs.json` map
  2) use that map with `pull_outputs.py` to copy outputs back to storage.

### Directory Layout

```text
rebuild_json/
├── 01_run_manual_build_outputs_json.sh
├── 02_run_manual_pull_outputs.sh
├── scripts/
│   ├── manual_build_outputs_json.py
│   └── manual_pull_outputs.sh
├── results/
│   ├── outputs_json/
│   └── pull_outputs/
└── template_outputs_pvac7.0.0b1.json
```

### High-level Workflow
1) Clone `cloud-workflows`:
`git clone https://github.com/wustl-oncology/cloud-workflows.git`

2) Build repointed outputs JSON:
`bash 01_run_manual_build_outputs_json.sh`

3) Pull outputs using rebuilt JSON:
`bash 02_run_manual_pull_outputs.sh`

### What `scripts/manual_build_outputs_json.py` Does
- Uses a successful run `outputs.json` as a structural template.
- Scans files under the new run scratch workflow directory (`call-*/.../execution/...`).
- Rewrites template output paths to new run paths by normalized key matching:
  - normalizes UUID path segments
  - supports sample prefix normalization in filenames:
    - `--template-sample-id` for old/template sample prefix
    - `--sample-id` for new-run sample prefix and output file naming
- Includes FastQC fallback mapping for SRR-name changes:
  - if direct match fails for `*_1_fastqc.zip` or `*_2_fastqc.zip`,
  - matches by parent call path + mate number (`1`/`2`) while tolerating glob hash changes.
- Expands `outputs["immuno.pVACseq"]["mhc_i"]` and `["mhc_ii"]`:
  - finds mapped `glob-*` parent directories
  - includes all files under those directories (not just template-listed files).
- Expands `outputs["immuno.somatic"]["cnv"]["cnvkit"]` BED entries:
  - discovers all `*.bed` files under mapped CNVkit `execution` directory/directories
  - replaces template-specific BED file entries with discovered BED paths.
- Prints summary stats, including counts for:
  - rewritten paths
  - FastQC fallback rewrites
  - pVACseq list expansions
  - CNVkit BED expansion.

### Runner Scripts
- `01_run_manual_build_outputs_json.sh` runs:
  - `scripts/manual_build_outputs_json.py`
  - and writes `results/outputs_json/<sample_id>_outputs.json`
- `02_run_manual_pull_outputs.sh` runs:
  - `scripts/manual_pull_outputs.sh`
  - and writes `results/pull_outputs/<sample_id>_out`
- `scripts/manual_pull_outputs.sh` wraps `cloud-workflows/scripts/pull_outputs.py` using:
  - `--cloud-workflows-dir`
  - `--json-file`
  - `--outputs-dir`
- `scripts/manual_build_outputs_json.py` writes:
  - `results/outputs_json/<sample_id>_outputs.json`

### Notes
- Current template was created from a run using:
  - `susannakiwala/pvactools:7.0.0b1_ml_predictor3`

