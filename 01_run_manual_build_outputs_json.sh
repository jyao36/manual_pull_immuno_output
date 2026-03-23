# Change directory to the script directory
cd "$(dirname "$0")"

# Change these to the sample ID you are processing, and the large scratch directory where the immuno pipeline outputs are stored
sample_id="Hu_159"
immuno_dir_large="scratch1/fs1/mgriffit/jyao/pipeline_test/Hu_159_attempt2/cromwell-executions/immuno/fa804bb0-48fd-484b-8df3-f70e212fe756"

python3 "scripts/manual_build_outputs_json.py" \
  --template "template_outputs_pvac7.0.0b1.json" \
  --scratch-dir "${immuno_dir_large}" \
  --sample-id "${sample_id}" \
  --template-sample-id "Hu_159" \
  --out-dir "results/outputs_json"