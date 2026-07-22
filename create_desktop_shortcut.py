import os

def make_shortcut():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop, "FORGE.lnk")
    
    # Remove old Servent AI shortcut if present
    old_shortcut = os.path.join(desktop, "Servent AI.lnk")
    if os.path.exists(old_shortcut):
        try:
            os.remove(old_shortcut)
        except Exception:
            pass

    target_vbs = os.path.abspath("FORGE.vbs")
    working_dir = os.path.abspath(".")

    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'Set oLink = WshShell.CreateShortcut("{shortcut_path}")\n'
        'oLink.TargetPath = "wscript.exe"\n'
        f'oLink.Arguments = """{target_vbs}"""\n'
        f'oLink.WorkingDirectory = "{working_dir}"\n'
        'oLink.Description = "FORGE AI Desktop App"\n'
        'oLink.Save\n'
    )
    
    temp_vbs = os.path.abspath("make_lnk.vbs")
    with open(temp_vbs, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    os.system(f'cscript //nologo "{temp_vbs}"')
    if os.path.exists(temp_vbs):
        os.remove(temp_vbs)
    print(f"FORGE Desktop Shortcut created at: {shortcut_path}")

if __name__ == "__main__":
    make_shortcut()
