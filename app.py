import streamlit as st
import os
import tempfile
import shutil
import ast
import stat
import time
from git import Repo, GitCommandError
from datetime import datetime
import requests

# Clone repo (shallow or full)
def clone_repo(repo_url, to_path, shallow=True):
    try:
        if shallow:
            Repo.clone_from(repo_url, to_path, depth=1)
        else:
            Repo.clone_from(repo_url, to_path)
        return True, ""
    except GitCommandError as e:
        return False, str(e)

# Get .py files from repo
@st.cache_data
def get_python_files(repo_path):
    py_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files

# Parse functions from a .py file with details
def parse_functions_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read())
        funcs = []
        for n in ast.walk(node):
            if isinstance(n, ast.FunctionDef):
                docstring = ast.get_docstring(n)
                args = [arg.arg for arg in n.args.args]
                funcs.append({
                    "name": n.name,
                    "args": args,
                    "docstring": docstring or ""
                })
        funcs.sort(key=lambda f: f["name"])
        return funcs
    except Exception as e:
        return [{"name": f"⚠️ Error parsing {os.path.basename(file_path)}", "args": [], "docstring": str(e)}]

# Rank files by git commit activity
def rank_files_by_git_activity(repo_path, files):
    repo = Repo(repo_path)
    file_commit_dates = {}
    for f in files:
        rel_path = os.path.relpath(f, repo_path)
        commits = list(repo.iter_commits(paths=rel_path, max_count=5))
        if commits:
            commit_date = datetime.fromtimestamp(commits[0].committed_date)
            file_commit_dates[f] = commit_date
        else:
            file_commit_dates[f] = datetime(1970, 1, 1)
    return sorted(file_commit_dates.items(), key=lambda x: x[1], reverse=True)

# Build repo tree
def build_repo_tree(py_files, repo_root):
    tree = {}
    for file_path in sorted(py_files):
        rel_path = os.path.relpath(file_path, repo_root)
        parts = rel_path.split(os.sep)
        current_level = tree
        for part in parts[:-1]:
            current_level = current_level.setdefault(part, {})
        current_level[parts[-1]] = parse_functions_from_file(file_path)
    return tree

# Render tree
def render_tree(tree, parent_path=""):
    for key in sorted(tree.keys()):
        value = tree[key]
        if isinstance(value, dict):
            st.markdown(f"**📁 {key}**")
            with st.container():
                render_tree(value, os.path.join(parent_path, key))
        else:
            if value:
                st.markdown(f"- 📄 **{key}**")
                for func in value:
                    args = ", ".join(func["args"])
                    st.markdown(f"    - ⚙️ `{func['name']}({args})`")
            else:
                st.markdown(f"- 📄 {key} _(no functions found)_")

# Handle read-only files
def force_remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Cleanup temp directory
def cleanup_temp_dir(path, retries=5, delay=1):
    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=force_remove_readonly)
            return True
        except PermissionError:
            time.sleep(delay)
    return False

# Call summarizer microservice
def call_summarizer_api(code_snippet):
    try:
        response = requests.post(
            "http://127.0.0.1:8000/summarize",
            json={"code": code_snippet},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("summary", "No summary returned.")
    except Exception as e:
        return f"Error calling summarizer API: {e}"

# --- Streamlit UI ---
st.set_page_config(page_title="Onboarding Buddy", layout="wide")
st.title("🚀 Onboarding Buddy - Tree View & GPT Code Summary")

repo_url = st.text_input("Enter GitHub repo URL (public):", value="https://github.com/psf/requests")
shallow_clone = st.checkbox("Use shallow clone (faster)", value=True)

if st.button("Analyze Repo"):
    if not repo_url.strip():
        st.error("Please enter a valid GitHub repo URL.")
    else:
        temp_dir = tempfile.mkdtemp()
        try:
            with st.spinner("Cloning repo..."):
                success, err = clone_repo(repo_url, temp_dir, shallow_clone)
                if not success:
                    st.error(f"Failed to clone repo: {err}")
                else:
                    st.success("Repo cloned successfully!")
                    with st.spinner("Analyzing Python files..."):
                        py_files = get_python_files(temp_dir)
                        if not py_files:
                            st.warning("No Python files found in the repo.")
                        else:
                            ranked_files = rank_files_by_git_activity(temp_dir, py_files)
                            repo_tree = build_repo_tree(py_files, temp_dir)

                            # Sidebar ranked files with dates
                            st.sidebar.header("📌 Ranked Python Files")
                            options = [
                                f"{os.path.relpath(f, temp_dir)} ({dt.strftime('%Y-%m-%d')})"
                                for f, dt in ranked_files
                            ]
                            selected_option = st.sidebar.radio("Select a file:", options)
                            selected_index = options.index(selected_option)
                            selected_file = ranked_files[selected_index][0]

                            # Main: Repo tree
                            st.header("📂 Repository Structure")
                            render_tree(repo_tree)

                            # Read full code from selected file
                            with open(selected_file, "r", encoding="utf-8") as f:
                                code_text = f.read()

                            # Call summarizer API on full file code
                            st.header(f"📝 GPT-powered Code Summary: {selected_option}")
                            summary = call_summarizer_api(code_text)
                            st.text_area("Summary", summary, height=300)

        finally:
            success = cleanup_temp_dir(temp_dir)
            if not success:
                st.warning(f"Could not fully remove temp dir {temp_dir}. You may need to delete it manually.")
