import os
import pandas as pd


def remove_csvs_with_quoted_404_content(folder_path="./website"):
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)
            try:
                df = pd.read_csv(file_path)
                if 'content' in df.columns and (df['content'] == '"404 Not Found').any():
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")


def merge_csvs_remove_duplicates(folder_path='./website', output_folder='./data', output_filename='merged_output.csv'):
    all_dataframes = []

    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Loop through all CSV files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            try:
                df = pd.read_csv(file_path)
                all_dataframes.append(df)
            except Exception as e:
                print(f"Could not read {file_path}: {e}")

    # Merge and remove duplicates
    if all_dataframes:
        merged_df = pd.concat(all_dataframes, ignore_index=True)
        merged_df.drop_duplicates(inplace=True)
        
        # Define the output file path
        output_path = os.path.join(output_folder, output_filename)
        merged_df.to_csv(output_path, index=False)
        print(f"Merged CSV saved to {output_path}")
    else:
        print("No readable CSV files found in the specified folder.")

# Example usage:
merge_csvs_remove_duplicates()
