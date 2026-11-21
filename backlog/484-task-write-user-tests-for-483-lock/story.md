As an operator of the shared funnel, I need merges into provisioning and main to be serialized by a lock and gated by guard check, so parallel approvals cannot corrupt the shared refs.
