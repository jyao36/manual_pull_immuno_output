# Change directory to the script directory
cd "$(dirname "$0")"

python3 "manual_build_outputs_json.py" \
  --template "template_outputs.json" \
  --scratch-dir "/scratch1/fs1/mgriffit/jyao/pipeline_test/Hu_159_attempt2/cromwell-executions/immuno/fa804bb0-48fd-484b-8df3-f70e212fe756" \
  --sample-id "Hu_159_attempt2" \
  --out-dir "results/repoint_outputs_json"