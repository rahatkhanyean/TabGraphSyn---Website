import os
import shutil

# Path to the original file
original_file = os.path.join('src', 'relgdiff', 'data', 'tables_to_heterodata.py')

# Create a backup
backup_file = original_file + '.bak'
if not os.path.exists(backup_file):
    shutil.copy(original_file, backup_file)
    print(f"Created backup at {backup_file}")

# Read the file content
with open(original_file, 'r') as f:
    content = f.read()

# Check if our modification is already present
if "# Add self-relations for single table case" not in content:
    # Find the position to insert our code
    # We'll add it inside the tables_to_heterodata function, right before the return statement
    pos = content.rfind("return data")
    
    # Our code to add
    code_to_add = """
    # Add self-relations for single table case
    # This ensures there are edges in the heterogeneous graph
    if len(data.metadata()[1]) == 0:
        print("No edge types found. Adding self-relation edges for single table.")
        
        # Add a self-relation for the embedding_table
        if embedding_table:
            import torch
            from torch_geometric.nn import knn_graph
            
            # Get the features for the table
            x = data[embedding_table].x
            
            # Create edges connecting each node to its 5 nearest neighbors
            k = min(5, x.size(0) - 1)  # avoid k larger than number of nodes
            if k > 0:
                edge_index = knn_graph(x, k=k, flow='source_to_target')
                
                # Add these edges to the heterogeneous data object
                data[(embedding_table, 'similar_to', embedding_table)].edge_index = edge_index
                print(f"Added {edge_index.size(1)} 'similar_to' edges for {embedding_table}")
    
    """
    
    # Insert our code
    modified_content = content[:pos] + code_to_add + content[pos:]
    
    # Write the modified content back
    with open(original_file, 'w') as f:
        f.write(modified_content)
    
    print(f"Modified {original_file} to add self-relations for single tables")
else:
    print("Modification already present")

print("Done! Try running your training command again.") 