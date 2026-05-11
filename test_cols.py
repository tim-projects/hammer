import os
try:
    print(os.get_terminal_size().columns)
except:
    print("fail")
