# Change directory to the script directory
cd "$(dirname "$0")"

# Change this to the sample ID you are processing
sample_id="Hu_159"
# Change this to the directory where the cloud-workflows repository is cloned
cloud_workflows_dir="/storage1/fs1/mgriffit/Active/griffithlab/pipeline_test/jennie/ml_itb_test/cloud-workflows"

bash scripts/manual_pull_outputs.sh \
--cloud-workflows-dir "${cloud_workflows_dir}" \
--json-file "results/outputs_json/${sample_id}_outputs.json" \
--outputs-dir "results/pull_outputs/${sample_id}_out"