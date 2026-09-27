"""Hide only the native asset reference for a file the worker has deleted."""
from pathlib import Path


def prune_history_output(queue, output_root, path):
    """Keep jobs and sibling outputs; remove only this file's output metadata."""
    target = Path(path).resolve()
    root = Path(output_root).resolve()
    def matches(item):
        if not isinstance(item, dict) or item.get('type') != 'output' or not item.get('filename'):
            return False
        candidate = (root / item.get('subfolder', '') / item['filename']).resolve()
        return candidate.is_relative_to(root) and candidate == target
    with queue.mutex:
        for job in queue.history.values():
            for output in job.get('outputs', {}).values():
                if not isinstance(output, dict):
                    continue
                for key, values in list(output.items()):
                    if isinstance(values, list):
                        output[key] = [item for item in values if not matches(item)]


def hide_deleted_asset(path):
    from server import PromptServer
    import folder_paths
    from app.database.db import can_create_session, create_session
    from app.assets.database.queries.asset_reference import get_reference_by_file_path
    from app.assets.services import delete_asset_reference
    if Path(path).exists():
        raise ValueError('Refusing to hide a file that still exists')
    prune_history_output(PromptServer.instance.prompt_queue, folder_paths.get_output_directory(), path)
    if not can_create_session():
        return True
    refs = {}
    with create_session() as session:
        for spelling in {str(Path(path)), Path(path).as_posix()}:
            ref = get_reference_by_file_path(session, spelling)
            if ref is not None:
                refs[ref.id] = ref.owner_id
    for reference_id, owner in refs.items():
        if not delete_asset_reference(reference_id, owner, delete_content_if_orphan=False):
            raise ValueError('Native asset reference could not be hidden')
    return True
