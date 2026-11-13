1. Grep every literal 'main' in tasks_ai/ and classify: config default vs gate/sync path
2. Fix get_default_branch to return the first existing default branch
3. Route gate/sync/merge/archive paths through the derived value; keep fixtures' expectations
4. Add master-named repo end-to-end test; add no-default-branch error test
5. Run ./hammer check all
6. Gates and sync assume main while repos may use master