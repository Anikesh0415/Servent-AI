from src.logger import logger


def say_hello(name="World"):
    logger.info(f"PLUGIN TRIGGERED: Hello {name}!")
    return f"I have said hello to {name} via the plugin!"


def register_plugin(registry):
    registry.register(
        "hello_world", '{"action": "hello_world", "name": "person to greet"}', say_hello
    )
