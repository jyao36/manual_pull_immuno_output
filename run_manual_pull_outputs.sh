# Change directory to the script directory
cd "$(dirname "$0")"

sample_id="Hu_159"

bash manual_pull_outputs.sh \
--cloud-workflows-dir "/storage1/fs1/mgriffit/Active/griffithlab/pipeline_test/jennie/ml_itb_test/cloud-workflows" \
--json-file "results/outputs_json/${sample_id}_outputs.json" \
--outputs-dir "results/pull_outputs/${sample_id}_out"