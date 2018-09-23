import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.constants import *
import random
from sc2.position import Point2, Point3


class DoNothinBot(sc2.BotAI):
	async def on_step(self, iteration):
		pass




class ChargeLotBot(sc2.BotAI):

	def __init__(self):
		self.current_attack_wave = 0

        # if an attack is ongoing we should reinforce
		self.attack_ongoing = False

		self.death_ball_location = None
		self.attack_location = None
		self.base_location = None

		self.death_ball_radius = 5

		self.last_observer_built = 0
		self.should_build_high_templar = False

		self.last_defense_check = 0

		self.last_storm_command = 0  # debug printing junk


	# build order excludes pylons and army units
	build_order = [
			NEXUS,  # always have a nexus first, in case it gets destroyed, rebuild.
			PYLON,  # build pylon right away
			GATEWAY,
			ASSIMILATOR,
			CYBERNETICSCORE,
			GATEWAY,
			ASSIMILATOR,
			NEXUS,
			TWILIGHTCOUNCIL,
			GATEWAY,
			ROBOTICSFACILITY,
			GATEWAY,
			FORGE,
			GATEWAY,
			ASSIMILATOR,
			ASSIMILATOR,
			TEMPLARARCHIVE,
			GATEWAY,
			ROBOTICSBAY,
			NEXUS,
			ROBOTICSFACILITY,
			GATEWAY,
			NEXUS,
			ASSIMILATOR,
			GATEWAY,
			ASSIMILATOR,
			STARGATE,
			GATEWAY,
			NEXUS,
			GATEWAY,
			ASSIMILATOR,
			ROBOTICSFACILITY,
			ASSIMILATOR,
			GATEWAY,
			NEXUS,
			GATEWAY,
			ASSIMILATOR,
			ASSIMILATOR,
			GATEWAY,
			FLEETBEACON,
			NEXUS,
			ASSIMILATOR,
			ASSIMILATOR,
			GATEWAY,
			NEXUS,
			ASSIMILATOR,
			ASSIMILATOR,
			]

	# specifies next desired upgrade
	upgrades_wanted = [
		RESEARCH_CHARGE,
		FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1,
    	FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2,
    	FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1,
    	RESEARCH_PSISTORM,
    	FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3,
    	FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2,
    	RESEARCH_EXTENDEDTHERMALLANCE,
    	FORGERESEARCH_PROTOSSGROUNDARMORLEVEL3,
		FORGERESEARCH_PROTOSSSHIELDSLEVEL1,
		FORGERESEARCH_PROTOSSSHIELDSLEVEL2,
		FORGERESEARCH_PROTOSSSHIELDSLEVEL3,
		]

	#specifies the number of unites involved in each attack wave
	attack_wave = [
		10,
		15,
		20,
		25,
	]


	async def on_step(self, iteration):
		await self.distribute_workers()
		await self.build_workers()
		await self.build_buildings()
		await self.build_army()
		await self.assemble_death_ball()
		await self.defend()
		await self.upgrade()
		await self.scout()
		await self.try_to_storm()

	async def try_to_storm(self):
		if len(self.known_enemy_units.not_structure) == 0:
			for high_templar in self.units(HIGHTEMPLAR):
				if PSISTORM_PSISTORM in high_templar.orders:
					await self.do(high_templar.stop())
			return
		#storm_dist = self._game_data.abilities[PSISTORM_PSISTORM]._proto.cast_range
		for high_templar in self.units(HIGHTEMPLAR):
			abilities = await self.get_available_abilities(high_templar)
			if PSISTORM_PSISTORM in abilities:
				closest_enemy = self.known_enemy_units.not_structure.closest_to(high_templar.position)
				# look for all known enemies within 3 unites of the closest, and then find the center
				enemy_center = self.known_enemy_units.not_structure.closer_than(3, closest_enemy.position).center
				print ("trying to storm at ", enemy_center, " hit ", closest_enemy.position)
				await self.do(high_templar(PSISTORM_PSISTORM, enemy_center))


	async def scout(self):
		observers = self.units(OBSERVER)
		if len(observers) > 0 and observers[0].is_idle:
			await self.do(observers[0].move(self.enemy_start_locations[0].random_on_distance(20)))
		if len(observers) > 1 and observers[1].is_idle:
			await self.do(observers[1].move(self.main_base_ramp.top_center.random_on_distance(20)))
		if len(observers) > 2 and observers[2].is_idle and self.death_ball_location:
			# last observers is 3 positions behind the death ball
			observer_location = self.death_ball_location
			if self.death_ball_location.distance_to(self.base_location) != 0:
				observer_location = self.death_ball_location.towards(self.base_location, 3)
			await self.do(observers[2].move(observer_location))


	async def upgrade(self):
		upgrade_buildings = self.units(TWILIGHTCOUNCIL).ready.noqueue + self.units(TEMPLARARCHIVE).ready.noqueue + self.units(ROBOTICSBAY).ready.noqueue +  self.units(FORGE).ready.noqueue
		for upgrade in ChargeLotBot.upgrades_wanted:
			for building in upgrade_buildings:
				abilities = await self.get_available_abilities(building)
				if upgrade in abilities and self.can_afford(upgrade): 
					await self.do(building(upgrade))
					if upgrade == RESEARCH_PSISTORM:
						self.should_build_high_templar = True
					break

	async def build_workers(self):
		nexuses = self.units(NEXUS).ready
		total_probes_i_want = len(nexuses) * 20
		if total_probes_i_want > 80:
			total_probes_i_want = 80
		if len(self.units(PROBE)) > total_probes_i_want:
			return
		for nexus in self.units(NEXUS).ready.noqueue:
			if self.can_afford(PROBE):
				await self.do(nexus.train(PROBE))

	async def build_pylon(self):
		nexuses = self.units(NEXUS)
		if not nexuses.exists:
			return
		build_near = nexuses.random.position.to2
		# get the closest minerals and build in the opposite direction
		closest = None
		closest_dist = 9000
		for mf in self.state.mineral_field:
			dist = build_near.distance_to(mf.position.to2)
			if closest == None or dist < closest_dist:
				closest_dist = dist
				closest = mf.position.to2
		newX = build_near.x - (closest.x - build_near.x)
		newY = build_near.y - (closest.y - build_near.y)
		build_near = Point2((newX, newY))
		if build_near is not None and self.can_afford(PYLON):
			await self.build(PYLON, near=build_near)


	async def build_buildings(self):
		build_next = self.choose_building_from_list()
		if (build_next == None):
			return
		if (build_next == PYLON):
			await self.build_pylon()
			return
		if (build_next == NEXUS):
			await self.expand()
			return
		if (build_next == ASSIMILATOR):
			await self.build_assimilator()
			return
		pylons = self.units(PYLON).ready
		if pylons.exists and self.can_afford(build_next):
			build_near= pylons.random
			await self.build(build_next, near=build_near)

	async def build_army(self):
		total_nexuses = len(self.units(NEXUS).ready)
		wanted_stalkers = total_nexuses * 4
		wanted_high_templar = 5

		robos = self.units(ROBOTICSFACILITY).ready.noqueue
		for robo in robos:
			if self.units(ROBOTICSBAY).ready.exists:
				if self.can_afford(COLOSSUS):
					await self.do(robo.train(COLOSSUS))
				if self.minerals < 300:
					# lets just wait for building colossus
					return
		for robo in robos:
			if self.can_afford(OBSERVER) and len(self.units(OBSERVER)) < 3:
				# limit observer building or we get gas starved
				if self.time - self.last_observer_built > 60:
					await self.do(robo.train(OBSERVER))
					self.last_observer_built = self.time
			elif self.can_afford(IMMORTAL):
				await self.do(robo.train(IMMORTAL))
		if len(robos) > 1 and self.minerals < 450:
			# prioritize robo units, unless we have a crazy amount of minerals
			return

		gateways = self.units(GATEWAY).ready.noqueue
		for gateway in gateways:
			if self.can_afford(HIGHTEMPLAR) and self.units(TEMPLARARCHIVE).ready.exists and len(self.units(HIGHTEMPLAR)) <= wanted_high_templar and self.should_build_high_templar:
				await self.do(gateway.train(HIGHTEMPLAR))
			if self.can_afford(STALKER) and self.units(CYBERNETICSCORE).ready.exists and len(self.units(STALKER)) <= wanted_stalkers:
				await self.do(gateway.train(STALKER))
			elif self.can_afford(ZEALOT):
				if self.vespene < 200 or self.minerals > 500:
					# This prevents too many zealots when we have lots of gas, but if we have lots of minerals build them anyhow
					await self.do(gateway.train(ZEALOT))

	def get_army(self):
		# this is the f2 key
		army_unit_types = [STALKER, IMMORTAL, ZEALOT, COLOSSUS, HIGHTEMPLAR]
		army = []
		for unit_type in army_unit_types:
			army.extend(self.units(unit_type))
		return army

	async def assemble_death_ball(self):
		if self.attack_location == None:
			self.attack_location = self.enemy_start_locations[0]

		if self.base_location == None:
			self.base_location = self.main_base_ramp.top_center

		self.move_death_ball_location()

		# can't morph archons yet maybe -- https://github.com/Blizzard/s2client-api/issues/279

		army_front = self.units(ZEALOT).idle
		death_ball_front = self.death_ball_location.towards(self.attack_location, 3)
		for unit in army_front:
			dist = self.death_ball_location.distance_to(unit.position.to2)
			if dist > self.death_ball_radius:
				await self.do(unit.attack(death_ball_front))

		army_middle = self.units(STALKER).idle + self.units(IMMORTAL).idle
		for unit in army_middle:
			dist = self.death_ball_location.distance_to(unit.position.to2)
			if dist > self.death_ball_radius:
				await self.do(unit.attack(self.death_ball_location))

		army_rear = self.units(COLOSSUS).idle + self.units(HIGHTEMPLAR).idle
		death_ball_rear = self.death_ball_location
		if self.death_ball_location.distance_to(self.base_location) != 0:
			self.death_ball_location.towards(self.base_location, 3)
		for unit in army_rear:
			dist = self.death_ball_location.distance_to(unit.position.to2)
			if dist > self.death_ball_radius:
				await self.do(unit.attack(death_ball_rear))

	def move_death_ball_location(self):
		if self.death_ball_location == None:
			self.death_ball_location = self.main_base_ramp.top_center

		num_army_in_death_ball = 0
		army = self.get_army()
		for unit in army:
			if unit.distance_to(self.death_ball_location) < self.death_ball_radius:
				num_army_in_death_ball += 1
		if len(army) < (ChargeLotBot.attack_wave[self.current_attack_wave] / 3) and self.attack_ongoing:
			# oops that attack failed, RETREAT!
			print ("Attack failed, retreat!")
			self.death_ball_location = self.base_location
			self.attack_ongoing = False
			if len(ChargeLotBot.attack_wave) > self.current_attack_wave - 1:
				self.current_attack_wave += 1
		elif len(army) > ChargeLotBot.attack_wave[self.current_attack_wave]:
			percent_army_in_death_ball = float(num_army_in_death_ball) / float(len(army)) * 100.0
			if (percent_army_in_death_ball > 60):
				if self.death_ball_location.distance_to(self.attack_location) != 0:
					self.death_ball_location = self.death_ball_location.towards(self.attack_location, 10)
					self.attack_ongoing = True
					print ("moving death ball location ", self.death_ball_location)


	def choose_building_from_list(self):
		if self.supply_left < 5 and not self.already_pending(PYLON):
			return PYLON
		tmp = {}
		for wanted_building in ChargeLotBot.build_order:
			if wanted_building not in tmp: 
				tmp[wanted_building] = 1
			else:
				tmp[wanted_building] += 1
			if tmp[wanted_building] > len(self.units(wanted_building)):
				return wanted_building
		return None

	def choose_next_building(self):
		if self.supply_left < 5 and not self.already_pending(PYLON):
			return PYLON

		total_gateways = len(self.units(GATEWAY).ready) + self.already_pending(GATEWAY)
		total_forges = len(self.units(FORGE).ready) + self.already_pending(FORGE)
		total_cores = len(self.units(CYBERNETICSCORE).ready) + self.already_pending(CYBERNETICSCORE)
		nexuses = self.units(NEXUS).ready

		# build a cybercore after gateway
		if total_gateways >= 1 and total_cores < 1:
			return CYBERNETICSCORE

		if total_forges < len(nexuses) and total_gateways >  3 * total_forges and total_forges < 3:
			return FORGE
		# build 4 gateways per nexus, but only if we need more.
		if total_gateways < len(nexuses) * 4:
			return GATEWAY
		if total_gateways >= 4 and not self.already_pending(TWILIGHTCOUNCIL) and len(self.units(TWILIGHTCOUNCIL).ready) == 0:
			return TWILIGHTCOUNCIL
		if len(self.units(TWILIGHTCOUNCIL).ready) > 0  and not self.already_pending(TEMPLARARCHIVE) and len(self.units(TEMPLARARCHIVE).ready) == 0:
			return TEMPLARARCHIVE
		return None

	async def build_assimilator(self):
		for nexus in self.units(NEXUS).ready:
			vespenes = self.state.vespene_geyser.closer_than(10.0, nexus)
			for vespene in vespenes:
				if not self.can_afford(ASSIMILATOR):
					break
				worker = self.select_build_worker(vespene.position)
				if worker is None:
					break
				if not self.units(ASSIMILATOR).closer_than(1.0, vespene).exists:
					await self.do(worker.build(ASSIMILATOR, vespene))

	async def expand(self):
		if self.can_afford(NEXUS):
			await self.expand_now()

	async def defend(self):
		if self.time - self.last_defense_check < 2:
			# this limits apm spamming
			return
		army = self.get_army()
		# only worry about enemies near the base
		enemies_near_my_base = []
		for enemy_unit in self.known_enemy_units:
			for nexus in self.units(NEXUS):
				if nexus.distance_to(enemy_unit) < 20:
					enemies_near_my_base.append(enemy_unit)
		army_near_my_base = []
		for unit in army:
			for nexus in self.units(NEXUS):
				if nexus.distance_to(unit) < 20:
					army_near_my_base.append(unit)
		if len(enemies_near_my_base) > 0:
			for unit in army_near_my_base:
				await self.do(unit.attack(random.choice(enemies_near_my_base).position))
				self.last_defense_check = self.time
		# TODO figure out if attack failed and we should buff up


	def find_target(self):
		if len(self.known_enemy_units) > 0:
			return random.choice(self.known_enemy_units).position
		elif len(self.known_enemy_structures) > 0:
			return random.choice(self.known_enemy_structures).position
		else:
			return self.enemy_start_locations[0]

	def on_unit_created(self, unit):
		# TODO this doesn't work because its missing await
		# self.do(unit.attack(self.main_base_ramp.top_center))
		pass

run_game(maps.get("AbyssalReefLE"), [
	Bot(Race.Protoss, ChargeLotBot()),
	Computer(Race.Terran, Difficulty.Hard)],
	realtime=False)