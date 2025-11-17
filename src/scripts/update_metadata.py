import os
import json
import pandas as pd
import argparse

def update_metadata_for_dataset(dataset_name):
    """
    Update the metadata file for a dataset based on its CSV file.
    
    Args:
        dataset_name: Name of the dataset (folder name)
    """
    base_path = os.path.join('src', 'data', 'original', dataset_name)
    csv_path = os.path.join(base_path, f'{dataset_name}.csv')
    metadata_path = os.path.join(base_path, 'metadata.json')
    
    print(f"Processing {dataset_name}...")
    
    # Read CSV
    try:
        df = pd.read_csv(csv_path)
        print(f"Found CSV file for {dataset_name} with {len(df)} rows and {len(df.columns)} columns")
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
        print(f"Please place your {dataset_name}.csv file in {base_path} directory")
        return
    
    # Read existing metadata
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print(f"Error: Metadata file not found at {metadata_path}")
        return
    
    # Get columns from CSV
    columns = df.columns.tolist()
    
    # Update metadata with columns
    for col in columns:
        # Skip if column already exists
        if col in metadata['tables'][dataset_name]['columns']:
            continue
        
        # Check if the column contains numeric or categorical data
        if pd.api.types.is_numeric_dtype(df[col]):
            sdtype = "numerical"
        else:
            sdtype = "categorical"
        
        # Add column to metadata
        metadata['tables'][dataset_name]['columns'][col] = {
            "sdtype": sdtype
        }
    
    # Add 'id' column if not exists (required for primary key)
    if 'id' not in metadata['tables'][dataset_name]['columns']:
        metadata['tables'][dataset_name]['columns']['id'] = {
            "sdtype": "id"
        }
    
    # Write updated metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Updated metadata for {dataset_name}")
    print(f"Total columns: {len(metadata['tables'][dataset_name]['columns'])}")

def main():
    parser = argparse.ArgumentParser(description='Update metadata files for datasets')
    parser.add_argument('--dataset', type=str, help='Name of the dataset to process')
    args = parser.parse_args()
    
    datasets = ['AIDS', 'MIMIC', 'TCGA', 'WBCD']
    
    if args.dataset:
        if args.dataset in datasets:
            update_metadata_for_dataset(args.dataset)
        else:
            print(f"Error: Dataset {args.dataset} not in the list of recognized datasets")
    else:
        for dataset in datasets:
            update_metadata_for_dataset(dataset)

if __name__ == "__main__":
    main() 