from abc import ABC, abstractmethod

class PipelineHook(ABC):
    @abstractmethod
    def execute(self, cli, task, current_state, new_status, filepath):
        pass

class HookRegistry:
    def __init__(self):
        self._enter_hooks = {}
        self._exit_hooks = {}

    def register_enter_hook(self, state, hook: PipelineHook):
        self._enter_hooks.setdefault(state, []).append(hook)

    def register_exit_hook(self, state, hook: PipelineHook):
        self._exit_hooks.setdefault(state, []).append(hook)

    def run_enter_hooks(self, cli, task, current_state, new_status, filepath):
        hooks = self._enter_hooks.get(new_status, [])
        for hook in hooks:
            hook.execute(cli, task, current_state, new_status, filepath)

    def run_exit_hooks(self, cli, task, current_state, new_status, filepath):
        hooks = self._exit_hooks.get(current_state, [])
        for hook in hooks:
            hook.execute(cli, task, current_state, new_status, filepath)
