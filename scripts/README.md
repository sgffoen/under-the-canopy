# Digital Tools - Workshop Setup

Grasshopper workflow to work with irregular and bifurcated branches.

## Setup Instructions

### 1. Download Rhino 8

Visit the [Rhinoceros website](https://www.rhino3d.com) and download **Rhino 8**.

- If you don't have a Rhino license, you can use the **90-day evaluation version** at no cost
- Install the software on your machine

### 2. Get the Repository

Choose one of the following based on your experience:

**Option A: Using Git (if you have Git installed)**
```bash
git clone <repository-url>
cd under-the-canopy
```

**Option B: Without Git**
- Download the repository as a ZIP file from the repository page
- Unzip the file to a location on your computer
- Navigate to the `under-the-canopy` folder

### 3. Initialize the Environment

- Open the `00_install.ghx` file in Grasshopper
- This script will automatically create a virtual environment and install all necessary libraries
- Wait for the installation to complete

## Understanding the Workflow

The Grasshopper files (`.ghx`) are the visual interface for this workflow. The Python scripts in the `src/` folder provide the core functionality used by these Grasshopper definitions.

### Source Code

The `src/` folder contains the Python modules that power the workflow:

- `branch.py` - Branch data structures and operations
- `centerline.py` - Centerline extraction and processing
- `graph_utils.py` - Graph-based utilities
- `growth_center.py` - Growth center calculations
- `helpers.py` - Helper functions
- `mesh_utils.py` - Mesh operations

You can inspect these files to understand the underlying algorithms and modify them as needed for your specific use case.


