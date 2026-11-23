1. 1. Wrap allocate_task_id body in store_lock
2. 2. Repoint create.py to the direct call and remove the shim import
3. 3. Add the lock-safety unit test and the guard-never-allocates pin
4. 4. Run tests/test_task_id_allocator.py + create-related tests + check all