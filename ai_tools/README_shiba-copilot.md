# ShibaCopilot: Grasshopper Installation & Usage Guide

**ShibaCopilot** brings the power of generative AI directly into your Grasshopper canvas. Follow these steps to install the plugin and start automating your computational design workflows.

---

## 🚀 Installation Steps

Because Grasshopper plugins often contain compiled libraries, following the unblocking procedure is essential for a successful installation.

### 1. Download and Unblock
* **Download**: Obtain the `ShibaCopilot.zip` file.
* **Unblock (Crucial)**: 
    1. Before extracting, **right-click** the ZIP file.
    2. Select **Properties**.
    3. At the bottom of the General tab, check the **Unblock** box (if present) and click **Apply/OK**. 
    *Note: Failing to do this may prevent the components from loading in Grasshopper.*

### 2. Extract and Move
* **Extract**: Unzip the entire folder.
* **Locate the Libraries Folder**: You need to move the extracted folder to your Grasshopper Libraries directory. You can find this in two ways:
    * **Manual Path**: `C:\Users\{YourUsername}\AppData\Roaming\Grasshopper\Libraries`
    * **Direct Access (Recommended)**: 
        1. Open Rhino and launch Grasshopper.
        2. In the Grasshopper menu, go to **File > Special Folders > Components Folder**.
* **Install**: Drag and drop the **entire extracted folder** into this directory.

### 3. Restart
* Close and restart both Rhino and Grasshopper to initialize the new components.

---

## 🔑 Configuration & Credentials

Upon first use, the plugin will require the following credentials to connect to the Shiba engine:

* **Username**: *[Enter any username you prefer]*
* **API Key**: `SHIBA2026`

---

## 💡 How to Use ShibaCopilot

Once installed, you will find ShibaCopilot within your Grasshopper tabs.

* **Generative Design**: Simply use the chat interface or prompt component to describe what you want to create.
* **Automation**: Ask the AI to generate geometry, set up data trees, or suggest specific component logic. 
* **Ready to Go**: Just ask whatever you want to create, and the system will generate the corresponding "stuff" directly on your canvas.

---

## 🎉 Happy Scripting!
You are now ready to leverage ShibaCopilot for your next computational project.
