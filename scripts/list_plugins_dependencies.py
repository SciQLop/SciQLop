import argparse
import os


def list_plugin_dependencies(plugins_dir):
    import json
    with open(os.path.join(plugins_dir, "plugin.json"), "r") as f:
        plugin_desc = json.load(f)
        return plugin_desc.get("python_dependencies", [])

def list_plugins_dependencies(plugins_dir):
    dependencies = []
    plugins = list(filter(lambda f: os.path.isdir(os.path.join(plugins_dir, f)) and not f.startswith('_'), os.listdir(plugins_dir)))
    for plugin in plugins:
        dependencies+=list_plugin_dependencies(os.path.join(plugins_dir, plugin))

    return set(dependencies)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List dependencies of plugins in a given directory")
    parser.add_argument("plugins_dir", type=str, help="Path to the plugins directory")
    args = parser.parse_args()

    deps = list_plugins_dependencies(args.plugins_dir)
    print(" ".join(deps))