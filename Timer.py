import asyncio
from asyncio import CancelledError


class Timer:
    def __init__(self):
        self.__tasks = {}

    def __store_task(self, task, tag):
        """
        Stores a task's Handle in the local dictionary.
        """
        self.__tasks[tag] = task

    async def __cancel_if_exists(self, tag):
        """
        Cancels the existing task by its Handle.
        """
        if tag in self.__tasks:
            task = self.__tasks[tag]
            task.cancel()
            try:
                await task
                self.__tasks.pop(tag)
            except CancelledError:

                print("Task {} is now cancelled.".format(tag))

    def __create_task(self, n, callback, tag):
        """
        Creates a new task with the given tag, and given delay.
        """

        async def _task():
            try:
                await asyncio.sleep(n)
                callback()
            except CancelledError:
                print("Task {} cancelled".format(tag))

        task = asyncio.create_task(_task())
        return task

    async def task_after_n_seconds(self, n: int, callback, tag):
        await self.__cancel_if_exists(tag)
        task = self.__create_task(n, callback, tag)
        self.__store_task(task, tag)
