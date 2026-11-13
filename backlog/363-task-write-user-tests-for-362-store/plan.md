1. Add a shared mode to store_lock (LOCK_SH) alongside the existing exclusive mode
2. Apply the shared lock to the store-read helpers: find_task, list/current rows, guard refresh
3. Add tests: reader-during-write (threads holding LOCK_EX), pending-change attribution, guard scan during move
4. Run the full suite and ./hammer check all
5. Store readers take no lock and observe mid-transaction state