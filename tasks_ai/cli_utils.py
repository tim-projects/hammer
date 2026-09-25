COLORS = {'HEADER': '\x1b[1;37m', 'PROGRESSING': '\x1b[1;32m', 'READY': '\x1b[1;33m', 'TESTING': '\x1b[1;35m', 'REVIEW': '\x1b[1;34m', 'STAGING': '\x1b[1;36m', 'DONE': '\x1b[0;32m', 'ARCHIVED': '\x1b[0;37m', 'RESET': '\x1b[0m', 'LINE': '\x1b[38;5;238m'}
PRIO_COLORS = {'1': '\x1b[1;31m', '2': '\x1b[31m', '3': '\x1b[33m', '9': '\x1b[37m'}

def format_table(headers, rows, status_idx=None, prio_idx=None):
    if not rows:
        return 'No data.'
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    L = COLORS['LINE']
    R = COLORS['RESET']
    output = []

    def b(left_border, m, r, sep='─┬─'):
        return f"{L}{left_border}{sep.join('─' * (w + 2) for w in widths)}{r}{R}"
    output.append(b('┌', '┬', '┐'))
    header_line = f'{L}│{R} ' + f' {L}│{R} '.join((f"{COLORS['HEADER']}{h:<{widths[i]}}{R}" for i, h in enumerate(headers))) + f' {L}│{R}'
    output.append(header_line)
    output.append(b('├', '┼', '┤'))
    for row in rows:
        formatted_row = []
        for i, cell in enumerate(row):
            cell_str = str(cell)
            color = ''
            reset = ''
            if status_idx is not None and i == status_idx:
                color = COLORS.get(cell_str, '')
                reset = COLORS['RESET'] if color else ''
            elif prio_idx is not None and i == prio_idx:
                color = PRIO_COLORS.get(cell_str, '')
                reset = COLORS['RESET'] if color else ''
            formatted_row.append(f'{color}{cell_str:<{widths[i]}}{reset}')
        row_str = f'{L}│{R} ' + f' {L}│{R} '.join(formatted_row) + f' {L}│{R}'
        output.append(row_str)
    output.append(b('└', '┴', '┘'))
    return '\n'.join(output)