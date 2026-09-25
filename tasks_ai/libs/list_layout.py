from ..cli_utils import format_table

def render_table(all_data):
    headers = ['#', 'P', 'Summary', 'Status', 'Type', 'Branch']
    rows = []
    for tasks in all_data.values():
        for t in tasks:
            rows.append([t['id'], t['p'], t['summary'], t['state'], t['type'], t['branch']])
    print(format_table(headers, rows, status_idx=3, prio_idx=1))