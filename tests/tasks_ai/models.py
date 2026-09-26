class Task:

    def __init__(self, metadata=None, parts=None):
        self.metadata = metadata or {}
        self.parts = parts or {}

    def __getitem__(self, key):
        return self.metadata.get(key)

    def __setitem__(self, key, value):
        self.metadata[key] = value

    def get(self, key, default=None):
        return self.metadata.get(key, default)

    @property
    def content(self):
        lines = [self.metadata.get('Ti', '')]
        parts_order = ['story', 'tech', 'criteria', 'plan', 'repro', 'notes', 'commits']
        for part in parts_order:
            if part in self.parts and self.parts[part].strip():
                header = part.replace('_', ' ').title()
                if part == 'story':
                    lines.append(f'\n## Context\n- **User Story**: {self.parts[part].strip()}')
                elif part == 'tech':
                    if 'story' in self.parts:
                        lines[-1] += f'\n- **Technical Background**: {self.parts[part].strip()}'
                    else:
                        lines.append(f'\n## Context\n- **Technical Background**: {self.parts[part].strip()}')
                else:
                    lines.append(f'\n## {header}\n{self.parts[part].strip()}')
        return '\n'.join(lines)