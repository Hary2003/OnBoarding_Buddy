import streamlit as st
import os
import tempfile
import shutil
import ast
import stat
import time
from git import Repo, GitCommandError
from datetime import datetime

# Clone repo (shallow)
def clone_repo(repo_url, to_path):
    try:
        Repo.clone_from(repo_url, to_path, depth=1)
        return True, ""
    except GitCommandError as e:
        return False, str(e)

# Get .py files from repo
def get_python_files(repo_path):
    py_files = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                py_files.append(os.path.join(root, file))
    return py_files

# Parse functions from a .py file
def parse_functions_from_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            node = ast.parse(f.read())
        return [n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
    except Exception:
        return []

# Rank Python files by recent Git activity
def rank_files_by_git_activity(repo_path, files):
    repo = Repo(repo_path)
    file_commit_dates = {}
    for f in files:
        rel_path = os.path.relpath(f, repo_path)
        commits = list(repo.iter_commits(paths=rel_path, max_count=5))
        if commits:
            most_recent_commit = commits[0]
            commit_date = datetime.fromtimestamp(most_recent_commit.committed_date)
            file_commit_dates[f] = commit_date
        else:
            file_commit_dates[f] = datetime(1970, 1, 1)
    return sorted(file_commit_dates.items(), key=lambda x: x[1], reverse=True)

# Summarize functions in a file
def summarize_file_functions(file_path):
    funcs = parse_functions_from_file(file_path)
    if not funcs:
        return "No functions found."
    return "Functions:\n" + "\n".join([f"- {f}" for f in funcs])

# Build nested dict tree representing repo file structure with functions
def build_repo_tree(py_files, repo_root):
    tree = {}
    for file_path in py_files:
        rel_path = os.path.relpath(file_path, repo_root)
        parts = rel_path.split(os.sep)

        current_level = tree
        for part in parts[:-1]:  # folder levels
            current_level = current_level.setdefault(part, {})

        # Add file and its functions
        funcs = parse_functions_from_file(file_path)
        current_level[parts[-1]] = funcs if funcs else []
    return tree

# Render the repo tree in Streamlit without nested expanders error
def render_tree(tree, parent_path=""):
    for key, value in tree.items():
        if isinstance(value, dict):
            # Folder - render as markdown header
            st.markdown(f"**📁 {key}**")
            with st.container():
                render_tree(value, os.path.join(parent_path, key))
        else:
            # File with functions list
            if value:  # functions present
                st.markdown(f"- 📄 **{key}**")
                for func in value:
                    st.markdown(f"    - ⚙️ {func}")
            else:
                st.markdown(f"- 📄 {key} _(no functions found)_")

# Safe removal of read-only files (Windows fix)
def force_remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Cleanup temp directory with retries to fix Windows PermissionError
def cleanup_temp_dir(path, retries=5, delay=1):
    for _ in range(retries):
        try:
            shutil.rmtree(path, onerror=force_remove_readonly)
            return True
        except PermissionError:
            time.sleep(delay)
    return False

# Streamlit UI
st.title("🚀 Onboarding Buddy - Tree View & Function Summary")

repo_url = st.text_input("Enter GitHub repo URL (public):", value="https://github.com/psf/requests")

if st.button("Analyze Repo"):
    if not repo_url.strip():
        st.error("Please enter a valid GitHub repo URL.")
    else:
        temp_dir = tempfile.mkdtemp()
        try:
            with st.spinner("Cloning repo..."):
                success, err = clone_repo(repo_url, temp_dir)
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

                            # Sidebar file selection (ranked) with radio for persistence
                            st.sidebar.header("Ranked Python Files by Recent Activity")
                            options = [os.path.relpath(f, temp_dir) for f, _ in ranked_files]
                            selected_option = st.sidebar.radio("Select a file to see function summary:", options)
                            selected_file = os.path.join(temp_dir, selected_option) if selected_option else None

                            # Main: Render repo tree structure with functions
                            st.header("Repository Structure")
                            render_tree(repo_tree)

                            # If a file selected in sidebar, show function summary
                            if selected_file:
                                st.header(f"File: {selected_option}")
                                summary = summarize_file_functions(selected_file)
                                st.text_area("Summary of functions", summary, height=200)

        finally:
            success = cleanup_temp_dir(temp_dir)
            if not success:
                st.warning(f"Could not fully remove temp dir {temp_dir}. You may need to delete it manually.")
