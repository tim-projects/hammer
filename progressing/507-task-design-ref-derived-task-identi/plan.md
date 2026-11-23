1. 1. Research done (this record's research field; operator notes /tmp/t verified)
2. 2. Create implementation task 'Implement ref-derived task id allocator' after this design is confirmed
3. 3. Allocator lands first with counter floor; task 495 then retires the counter, helpers, doctor block and seeding tests
4. 4. Task 501 builds its creation-time uniqueness check on the allocator's ref scan
5. 5. Only after that: 495 proceeds (its own criteria already assume ref-derived ids)