"""Execute the maintained notebook using the current research environment.

python -m research_pipeline.notebook --mode real_check
"""
import argparse
import os
from pathlib import Path
import nbformat
from nbclient import NotebookClient


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['exposure_study','real_check','real','synthetic_verification'], default='exposure_study')
    parser.add_argument('--output', type=Path, default=root/'notebooks/yodax_research_pipeline.ipynb')
    args = parser.parse_args()
    runtime = root/'data/research-notebook-runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    for key, subdir in [('MPLCONFIGDIR','matplotlib'),('IPYTHONDIR','ipython'),('JUPYTER_RUNTIME_DIR','jupyter')]:
        os.environ[key] = str(runtime/subdir)
    os.environ['YODAX_NOTEBOOK_MODE'] = args.mode
    notebook = nbformat.read(root/'notebooks/yodax_research_pipeline.ipynb', as_version=4)
    NotebookClient(notebook, timeout=600, kernel_name='python3',
                   resources={'metadata': {'path': str(root)}}).execute()
    nbformat.validate(notebook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, args.output)
    print(f'Executed {len(notebook.cells)} cells in {args.mode} mode: {args.output}')


if __name__ == '__main__':
    main()
