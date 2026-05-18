# ShibaCopilot: Grasshopper Installation & Usage Guide

**ShibaCopilot** brings generative AI directly into your Grasshopper canvas. Follow these steps to install and automate your computational design workflows.

---

## 🚀 Installation Steps

Grasshopper plugins often contain compiled libraries; following the unblocking procedure is essential.

### 1. Download and Unblock
* **Download**: Obtain the `ShibaCopilot.zip` file.
* **Unblock (Crucial)**: Before extracting, **right-click** the ZIP file, select **Properties**, check the **Unblock** box at the bottom of the General tab, and click **Apply/OK**. 
* **Note**: Failing to do this may prevent components from loading.

### 2. Extract and Move
* **Extract**: Unzip the entire folder.
* **Locate the Libraries Folder**: Move the extracted folder to your Grasshopper Libraries directory.
    * **Direct Access**: In Grasshopper, go to **File > Special Folders > Components Folder**.
* **Install**: Drag and drop the **entire extracted folder** into this directory.

### 3. Restart
* Close and restart both Rhino and Grasshopper to initialize the new components.

---

## 🔑 Configuration & Credentials

Upon first use, the plugin requires these credentials to connect to the Shiba engine:

* **Username**: [Enter any preferred username]
* **API Key**: `SHIBA2026`

---

## 💡 How to Use ShibaCopilot

ShibaCopilot interacts directly with your active workspace using a **Select & Prompt** workflow.

### 🛠 Modifying Existing Scripts
1. **Select** the specific components or script blocks you want to change.
2. **Describe** the modification in the prompt (e.g., *"Change the data tree structure to Graft"* or *"Optimize this C# script"*).
3. The AI will focus only on the **selected one** to modify.

### 🔗 Referencing Component Outputs
1. **Select** the component(s) whose output you want to use as context.
2. **Tell the LLM** what to do with that data (e.g., *"Take the points from this component and create a Voronoi pattern"*).
3. The system treats the selection as **context** for the new generation.

### ✨ Fresh Generation
* **Nothing Selected?** If no components are selected, ShibaCopilot will generate brand-new logic in an empty area of your canvas.

---

## ⚠️ Important Limitations
* **Multiple Instances**: **Do not try to open two instances of Rhino.**
* **System Conflict**: Running multiple Rhino windows simultaneously will cause the system to get confused and may break the AI connection.

---

## 🎉 Happy Scripting!
You are now ready to leverage ShibaCopilot for your next project.
