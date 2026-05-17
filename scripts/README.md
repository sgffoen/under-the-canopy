# FoC26 Workshop Setup

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

### 4. Grasshopper Scripts

After the environment is set up, the other Grasshopper files can be opened in order:

- `01_database.ghx` - Downloads OBJ branch meshes from the workshop database into the local `data/` folder.
- `02_branch_overview.ghx` - Loads the branch meshes and preprocesses them for inspection and overview.
- `03_centerline.ghx` - Computes branch centerlines, bifurcation points, and related centerline outputs.
- `04_scan_to_branch.ghx` - process 3D scanned branch.

## Understanding the Workflow

The Grasshopper files (`.ghx`) are the visual interface for this workflow. The Python scripts in the `src/` folder provide the core functionality used by these Grasshopper definitions. Geometry processing mostly done with [COMPAS](https://compas.dev/#/).

### Source Code

The `src/` folder contains the Python modules that power the workflow:

- `branch.py` - Branch preprocessing, bifurcation logic, and centerline methods
- `centerline.py` - Centerline extraction and centerline post-processing tools
- `database.py` - Google Drive database access and branch mesh download helpers
- `graph_utils.py` - Graph-based utilities for branch paths and bifurcations
- `growth_center.py` - Growth center calculations
- `helpers.py` - Shared helper functions, including grid layout tools
- `mesh_utils.py` - Mesh loading, preprocessing, and slicing helpers

You can inspect these files to understand the underlying algorithms and modify them as needed for your specific use case.


