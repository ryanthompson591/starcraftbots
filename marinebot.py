import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.constants import *
import random
import numpy as np


class MarineBot(sc2.BotAI):
  def __init__(self):
    self.ITERATIONS_PER_MINUTE = 165
    self.MAX_WORKERS = 50

    self.last_worker_distribution = 0

  async def on_step(self, iteration):
    self.iteration = iteration
    if self.time - self.last_worker_distribution > 5:
      # distribute workers every 5 seconds
      await self.distribute_workers()
    await self.build_workers()
    await self.build_supply()
    await self.get_gas()
    await self.build_baracks()
    await self.expand()
    await self.build_army()
    await self.move_army()

  async def build_workers(self):
    if (len(self.units(COMMANDCENTER)) * 22) > len(self.units(SCV)) and len(self.units(SCV)) < self.MAX_WORKERS:
      for cc in self.units(COMMANDCENTER).ready.noqueue:
        if self.can_afford(SCV):
          await self.do(cc.train(SCV))

  async def build_supply(self):
    if self.supply_left < 5 and not self.already_pending(SUPPLYDEPOT):
    	await self.build_supply_depot_now()
    elif self.supply_left < 1:
      await self.build_supply_depot_now()

  async def get_gas(self):
    if self.vespene > 100:
      # I'm just building marines, who needs gas!
      return
    if len(self.units(REFINERY)) >= 1 or not self.units(BARRACKS).exists or self.already_pending(REFINERY):
      # only ever need 1 refinery
      return
    
    for cc in self.units(COMMANDCENTER).ready:
      vaspenes = self.state.vespene_geyser.closer_than(10.0, cc)
      for vaspene in vaspenes:
        if not self.can_afford(REFINERY):
          break
        worker = self.select_build_worker(vaspene.position)
        if worker is None:
          break
        if not self.units(REFINERY).closer_than(1.0, vaspene).exists:
          await self.do(worker.build(REFINERY, vaspene))

  async def build_supply_depot_now(self):
    cc = self.units(COMMANDCENTER).ready
    if cc.exists:
      if self.can_afford(SUPPLYDEPOT):
        await self.build(SUPPLYDEPOT, near=cc.random.position.towards(self.game_info.map_center, 8))


  async def build_baracks(self):
    if not self.units(SUPPLYDEPOT).exists and not self.already_pending(SUPPLYDEPOT):
      await self.build_supply_depot_now()
    if not self.units(SUPPLYDEPOT).exists or not self.units(COMMANDCENTER).exists:
  		# can't build baracks without supply depot
      return
    cc = self.units(COMMANDCENTER).random
    if cc is None:
      # no CC can't do nothin'
      return

    if len(self.units(BARRACKS)) + self.already_pending(BARRACKS) < len(self.units(COMMANDCENTER)) * 4:
      if self.can_afford(BARRACKS):
        worker = self.select_build_worker(cc.position)
        if worker is not None:
          await self.build(BARRACKS, near=cc.position.towards(self.game_info.map_center, 8))

  async def expand(self):
    if self.units(COMMANDCENTER).amount < (self.iteration / self.ITERATIONS_PER_MINUTE) and self.can_afford(COMMANDCENTER):
      await self.expand_now()

  async def build_army(self):
    for barracks in self.units(BARRACKS).ready.noqueue:
      if self.can_afford(MARINE):
        await self.do(barracks.train(MARINE))

  async def move_army(self):
    if len(self.units(MARINE)) > 20:
      for marine in self.units(MARINE).idle:
        await self.do(marine.attack(self.enemy_start_locations[0]))


run_game(maps.get("AbyssalReefLE"), [
    Bot(Race.Terran, MarineBot()),
    Computer(Race.Zerg, Difficulty.Harder)
    ], realtime=False)
