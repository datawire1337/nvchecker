# MIT licensed
# Copyright (c) 2021,2026 lilydjwg <lilydjwg@gmail.com>, et al.

import asyncio
import string
import contextvars

from nvchecker.api import entry_waiter, BaseWorker, Entry, RawResult

class CombineFormat(string.Template):
  idpattern = '[0-9]+'

class Worker(BaseWorker):
  # Use a worker that doesn't hold the concurrency control semaphore
  # since we always wait for others.
  #
  # If we hold the semaphore, there may be more waiting tasks that available
  # concurrency, thus the execution hangs.

  async def run(self) -> None:
    futures = []
    for name, entry in self.tasks:
      ctx = contextvars.copy_context()
      fu = ctx.run(self.run_one, name, entry)
      futures.append(fu)

    for fu2 in asyncio.as_completed(futures):
      await fu2

  async def run_one(
    self, name: str, entry: Entry,
  ) -> None:
    try:
      version = await self.get_version(name, entry)
      await self.result_q.put(RawResult(name, version, entry))
    except Exception as e:
      await self.result_q.put(RawResult(name, e, entry))

  async def get_version(self, name, conf):
    t = CombineFormat(conf['format'])
    from_ = conf['from']
    waiter = entry_waiter.get()
    entries = [waiter.wait(name) for name in from_]
    vers = await asyncio.gather(*entries)
    versdict = {str(i+1): v for i, v in enumerate(vers)}
    return t.substitute(versdict)
