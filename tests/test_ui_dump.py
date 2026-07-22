import pywinauto

def dump_ui_tree():
    try:
        desktop = pywinauto.Desktop(backend="uia")
        win = desktop.active_window()
        if not win:
            return "No active window"
        
        controls = win.descendants()
        tree_elements = []
        for ctrl in controls[:50]: # limit to 50 for test
            name = ctrl.window_text()
            ctrl_type = ctrl.element_info.control_type
            if name:
                tree_elements.append(f"[{ctrl_type}] {name}")
                
        return "\n".join(tree_elements)
    except Exception as e:
        return str(e)

print(dump_ui_tree())
