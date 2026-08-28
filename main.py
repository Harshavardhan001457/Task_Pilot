"""Minimal, non-interactive demonstration entry point."""
from astra_sentinel import ActionRequest, build_default_runtime


if __name__ == "__main__":
    dispatcher, _audit = build_default_runtime()
    request = ActionRequest.create(capability="mock.echo", parameters={"message": "Sentinel ready"}, requester="cli")
    print(dispatcher.dispatch(request))
