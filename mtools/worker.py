"""Private stdio JSON-lines protocol. Only stderr may contain diagnostics."""
import json
import sys
from pathlib import Path
from .service import Service


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    service = None
    try:
        for line in sys.stdin:
            request = {}
            try:
                if len(line) > 44 * 1024 * 1024:
                    raise ValueError("Request too large")
                request = json.loads(line)
                if request.get("protocol_version") != 1:
                    raise ValueError("Protocol version mismatch")
                if request["method"] == "initialize":
                    if service:
                        raise ValueError("Already initialized")
                    service = Service(Path(__file__).resolve().parent.parent, request["params"]["host"])
                    result = service.status()
                elif request["method"] == "shutdown":
                    break
                elif service:
                    result = service.call(request["method"], request.get("params", {}))
                else:
                    raise ValueError("Initialize first")
                response = {"request_id": request.get("request_id"), "result": result}
            except Exception as e:
                response = {"request_id": request.get("request_id"), "error": {"message": str(e), "type": type(e).__name__}}
            print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    finally:
        if service:
            service.close()


if __name__ == "__main__":
    main()
