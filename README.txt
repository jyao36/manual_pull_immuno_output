Documentation: 

Purpose of this directory: 
I have been having issues with pulling outputs from the immuno run scratch directory. Runs seems to fail at the step when pulling
artifacts and exit with the error "OSError: [Errno 122] Disk quota exceeded". 
The outputs are left in /scratch, but final step fails to copy relevant outputs back to storage1. 

Solution I am working on: 
Since the workflow has ended when the job was exited, Cromwell server was terminated, and the script that fetches file path 
no longer works. I will make a script that manually maps relevant files in a `outputs.json` file. 
This file can be used by `pull_outputs.py` as a "map" to pull outputs from scratch to storage. 

Step 1: Clone cloud-workflows git repo
```git clone https://github.com/wustl-oncology/cloud-workflows.git```

Step 2: manual_build_outputs_json.py
This script take an existing outputs.json file (from Hu_159_out, a successful run) as a template, looks at the failed run 
scratch directory structure (/scratch1/fs1/mgriffit/jyao/pipeline_test/Hu_159_attempt2/cromwell-executions/immuno/fa804bb0-48fd-484b-8df3-f70e212fe756), and makes a new `outputs.repointed.json`
file for `Hu_159_attempt2`
Usage: bash run_manual_build_outputs_json.sh

Step 3: manual_pull_outputs.sh
Takes the new `outputs.json` and run `pull_outputs.py` from the cloud-workflows repo, and pull outputs into a specified output_dir.
Usage: bash run_manual_pull_outputs.sh 


NOTE:
* The template json file was made from a run using pvactools version: suannakiwala/pvactools:7.0.0b1_ml_predictor3

