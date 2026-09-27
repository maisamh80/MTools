"""Read the active graph's production data without running nodes."""
from pathlib import Path
from .mtools.files import inside
from .mtools.projects import ASSETS


def capture_project(graph, prompt, host, history):
    from .mtools.dependencies import validate_graph, analyze
    validate_graph(graph)
    if not isinstance(prompt, dict):
        raise ValueError('Expected an API prompt snapshot')
    files, warnings, texts = [], [], []
    for id, node in prompt.items():
        for key, value in node.get('inputs', {}).items():
            if not isinstance(value, str):
                if key.lower() in {'text', 'prompt', 'positive', 'negative', 'negative_prompt'} and isinstance(value, list):
                    warnings.append(f'Linked prompt at node {id}, {key}: connection is preserved in workflow JSON; evaluated text may not be available.')
                continue
            if key.lower() in {'text', 'prompt', 'positive', 'negative', 'negative_prompt'}:
                texts.append({'node': id, 'type': node.get('class_type'), 'input': key, 'text': value})
            if key.lower() in {'image', 'audio', 'video', 'file', 'filename', 'image_path', 'video_path', 'audio_path'}:
                name = value.removesuffix(' [input]').replace('\\', '/')
                if Path(name).suffix.lower() not in ASSETS:
                    continue
                try:
                    file = inside(host['input'], name)
                    if not file.is_file():
                        raise ValueError('File not found')
                    files.append({'role': 'references', 'path': name})
                except (ValueError, OSError):
                    warnings.append(f'Reference needs manual review: node {id}, {key}: {value}')
    matched = None
    for id, record in reversed(list(history.items())):
        entry = record.get('prompt', [])
        if len(entry) > 2 and entry[2] == prompt:
            matched = id
            for result in record.get('outputs', {}).values():
                for values in result.values():
                    if not isinstance(values, list):
                        continue
                    for value in values:
                        if isinstance(value, dict) and value.get('type') == 'output' and value.get('filename'):
                            files.append({'role': 'outputs', 'path': str(Path(value.get('subfolder', '')) / value['filename'])})
            break
    if matched is None:
        warnings.append('No exact matching execution in current ComfyUI history. Current graph saved; outputs were not guessed. Add outputs manually if needed.')
    if not any(f['role'] == 'outputs' for f in files):
        warnings.append('No associated final output was found.')
    report = analyze(graph, host)
    metadata = {'source': 'active-tab', 'execution_id': matched, 'prompt_fields': texts,
        'api_prompt': prompt, 'models': [{k:v for k,v in m.items() if k not in {'source','matches'}} for m in report['models']],
        'custom_nodes': report['custom_nodes'],
        'reference_detection': 'Recognized file inputs under ComfyUI input. Custom or external paths may require manual addition.'}
    return {'files': files, 'warnings': warnings, 'metadata': metadata,
            'prompt_text': '\n\n'.join(f"Node {t['node']} · {t['input']}\n{t['text']}" for t in texts)}
