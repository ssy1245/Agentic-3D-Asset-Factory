import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="启动本地角色参考工作室")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run("asset_factory.studio:create_app", factory=True, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
