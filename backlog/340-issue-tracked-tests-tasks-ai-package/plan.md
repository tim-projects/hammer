1. Grep the repo for anything importing tasks_ai expecting the tests/ copy; confirm nothing depends on it
2. git rm -r tests/tasks_ai; commit as part of the task branch
3. Add tests/conftest.py (or root conftest.py) inserting the project root at sys.path[0]
4. Add a regression test asserting tasks_ai.__path__[0] is the project package
5. Remove the now-unneeded per-file sys.path workaround from tests/test_store_concurrency.py and any other file that added one
6. Run the full suite and ./hammer check all
7. Tracked tests/tasks_ai package copy shadows the real package