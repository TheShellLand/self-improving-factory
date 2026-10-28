"""Start the audit and issue API."""
import uvicorn


def main():
    uvicorn.run("ui_backend.bridge:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
