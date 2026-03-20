#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage:"
  echo "  $0 --cloud-workflows-dir <path> --json-file <path> --outputs-dir <path> [--dryrun]"
  echo
  echo "Examples:"
  echo "  $0 --cloud-workflows-dir /path/to/cloud-workflows \\"
  echo "     --json-file /path/to/Sample_ID_manual_build_outputs.json \\"
  echo "     --outputs-dir /path/to/immuno_outputs/Sample_ID_out"
}

cloud_workflows_dir=""
json_file=""
outputs_dir=""
dryrun=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cloud-workflows-dir)
      cloud_workflows_dir="$2"
      shift 2
      ;;
    --json-file)
      json_file="$2"
      shift 2
      ;;
    --outputs-dir)
      outputs_dir="$2"
      shift 2
      ;;
    --dryrun)
      dryrun="--dryrun"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${cloud_workflows_dir}" || -z "${json_file}" || -z "${outputs_dir}" ]]; then
  echo "Error: --cloud-workflows-dir, --json-file, and --outputs-dir are required."
  usage
  exit 1
fi

# locate pull_outputs.py in cloud-workflows directory
pull_outputs_py="${cloud_workflows_dir}/scripts/pull_outputs.py"

if [[ ! -f "${pull_outputs_py}" ]]; then
  echo "Error: pull_outputs.py not found at ${pull_outputs_py}"
  exit 1
fi

# run pull_outputs.py
python3 "${pull_outputs_py}" \
  --outputs-file "${json_file}" \
  --outputs-dir "${outputs_dir}" \
  ${dryrun}