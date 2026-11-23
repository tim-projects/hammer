1. 1. Add the record-and-ref high-water allocator with the counter migration floor
2. 2. Move create allocation and parent/paired-child writes into one store lock transaction
3. 3. Add concurrent-create, fresh-clone, and reject-then-create acceptance tests
4. 4. Verify guard remains verification-only and run the relevant test suite