"""Start the audit and issue API."""
import uvicorn
from core.config import ApiConfig


class ApiServer:
    def __init__(self, config=None):
        self.config = config if config is not None else ApiConfig()

    def run(self):
        uvicorn.run("ui_backend.bridge:app", host=self.config.host, port=self.config.port)


def main():
    ApiServer().run()


if __name__ == "__main__":
    main()
