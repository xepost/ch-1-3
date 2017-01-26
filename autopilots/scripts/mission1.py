#!/usr/bin/env python


# Modules import 
import rospy
import numpy as np
import tf
import datetime

from math import *
from std_msgs.msg import *
from sensor_msgs.msg import *
from geometry_msgs.msg import *
from mavros_msgs.msg import *
from mavros_msgs.srv import *

from autopilots.msg import StateMachine, GripperFeedback, GripperAction

import autopilotLib
import myLib
import autopilotParams

# TODO: include the namespace in the following function
autopilotParams.setParams()

# TODO: move the gripper msg definition from autopilots pckg toi gripper pckg

#!!!!!!!!!!!!! Need to define a message type for the state machine !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
######################################################################################################
# structure of the StateMachine.msg
#	Headaer header
#	string	state
#	string	signal

#!!!!!!!!!!!!! Need to define a message type for the Gripper Feedback !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
########################################################################################################
# structure of the GripperFeedback.msg
#	Headaer header
#	bool[]	pushbutton_state	# holds the state of each pushbutton
#	bool	picked			# indicates an object is picked or not

#!!!!!!!!!!!!! Need to define a message type for the Gripper actuation !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#########################################################################################################
# structure of the GripperAction.msg
#	Headaer header
#	bool	command	# true: activate. false: deactivate


###### State Machine Class ######
# States: {Start, Idle, Takeoff, ObjectSearch, Picking, GoToDrop, WaitToDrop, Dropping, GoHome, Land}
# Possible Signals for each state:
#	Start:		{'Waiting', 'Ready'}
#	Takeoff:	{'Done', 'Running'}
#	ObjectSearch:	{'Done', 'Running'}
#	Picking:	{'Done', 'Running', 'Failed'}
#	GoToDrop:	{'Done', 'Running'}
#	Dropping:	{'Done', 'Running'}
#	GoHome:		{'Done', 'Running'}
#	Land:		{'Done', 'Running'}
class StateMachineC( object ):
	def __init__(self, ns):
		self.namespace		= ns				# ns: namespace [REQUIRED]. Always append it to subscribed/published topics
		self.areaBoundaries=    = []				# The list of the different field refence points (to be provided)
		self.cameraView		=1				#Parameter that caracterize the camera precision and field of view
		self.current_state	= 'Idle'			# Initially/finally, do nothing.
		self.current_signal	= None				# used to decide on transitions to other states
		self.erro_signal	= False				# to indicate error staus in state machine (for debug)
		self.error_str		= 'No error'			# Error description (for debug)
		self.DEBUG		= False				# Turn debug mode on/off
		self.START_SIGNAL	= False				# a flag to start the state machine, if true
		if(ns="/Quad1"):
			ns_other_1="/Quad2"
			ns_other_2="/Quad3"
		elif(ns="/Quad2"):
			ns_other_1="/Quad1"
			ns_other_2="/Quad3"
		elif(ns="/Quad3"):
			ns_other_1="/Quad1"
			ns_other_2="/Quad2"
		# internal state-related fields
		self.current_lat	= 0.0
		self.current_lon	= 0.0
		self.target_lat		=1.1
		self.target_lon		=1.1
		self.TKOFFALT		= 2.0				# takeoff altitude [m] to be set by external controller
		self.PRE_DROP_COORDS	= np.array([23.1, 12.1])	# Lat/Lon of pre-drop location: different for each vehicle
		self.DROP_COORDS	= np.array([23.3, 12.5])	

		self.ZGROUND		= 0.0				# Altitude at ground level
		self.home		= autopilotLib.xyzVar()
		self.PICK_ALT		= 0.6				# Altitude at which we pick object [m]
		self.CAMOFFSET		= 0.0				# [m]
		self.ENVELOPE_XY_POS	= 0.2				# relative pos error where descend is allowed [m]
		self.ENVELOPE_XY_V	= 0.1				# relative vel error where descend is allowed [m/s]

		# Instantiate a setpoint topic structure
		self.setp		= PositionTarget()
		self.setp.type_mask	= int('010111000111', 2)

		# Instantiate altitude controller object (from autopilot library)
		self.altK 		= autopilotLib.kAltVel(ns)

		# Instantiate body controller object (from autopilot library)
		self.bodK 		= autopilotLib.kBodVel(ns)
    
		# Instantiate a tracker (blue)
		self.blue_target 		= autopilotLib.xyzVar()		# xyz location of object w.r.t quad [m]. z only used to indicate if object is tracked or not
		rospy.Subscriber(ns+'/blue_xySp', Point32, self.blue_target.cbXYZ)

		# Instantiate a tracker (green)
		self.green_target 		= autopilotLib.xyzVar()
		rospy.Subscriber(ns+'/green_xySp', Point32, self.green_target.cbXYZ)

		# Establish a rate
		self.fbRate 		= rospy.get_param(ns+'/autopilot/fbRate')
		self.rate 		= rospy.Rate(self.fbRate)

		# Subscriber to mavros GPS topic
		rospy.Subscriber(ns+'/mavros/global_position/global', NavSatFix, self.gps_cb)
		# Subscriber to mavros others GPS topic
		rospy.Subscriber(ns_other_1+'/mavros/global_position/global', NavSatFix, self.gps_other_1_cb)
		rospy.Subscriber(ns_other_2+'/mavros/global_position/global', NavSatFix, self.gps_other_2_cb)
		
		# Subscriber to mavros others states topic
		rospy.Subscriber(ns_other_1+'/state_machine/state', StateMachine, self.state_other_1_cb)
		rospy.Subscriber(ns_other_2+'/state_machine/state', StateMachine, self.state_other_2_cb)


		# setpoint publisher (velocity to Pixhawk)
		self.command 		= rospy.Publisher(ns+'/mavros/setpoint_raw/local', PositionTarget, queue_size=10)

		# State Machine topic & its publisher 
		self.state_topic	= StateMachine()
		self.state_pub		= rospy.Publisher(ns+'/state_machine/state', StateMachine, queue_size=10)

		# Gripper feedback topic
		self.gripper_feedback	= GripperFeedback()
		rospy.Subscriber(ns+'/gripper_node/gripper_status', GripperFeedback, self.gripper_cb)

		# Gripper command topic
		self.gripper_action	= GripperAction()
		self.gripper_pub	= rospy.Publisher(ns+'/gripper_node/gripper_command', GripperAction, queue_size=10)


###### path tracker Class ######
class path_tracker( object ):
	def __init__(self):
		self.index
		self.start
		self.stop
		self.elapsed
		self.state
		self.way_points_list
	
	#----------------------------------------------------------------------------------------------------------------------------------------#
	#                                                   (States implementation)                                                              #

	# State: start
	def execute_start(self):
		self.current_state='Start'
		self.current_signal='Waiting'

		self.debug()

		while not self.START_SIGNAL and not rospy.is_shutdown():
			# do nothing, until we receive the start signal

			# publish state topic
			self.state_topic.state = self.current_state
			self.state_topic.signal = self.current_signal
			self.state_pub.publish(self.state_topic)

		self.current_signal = 'Ready'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)
		
		self.debug()
	
		return	
			
	
	# State: Takeoff
	def execute_takeoff(self):
		self.current_state = 'Takeoff'
		self.current_signal = 'Running'
		
		self.debug()
		
		# set the controllers setpoints
		self.altK.zSp = self.ZGROUND + rospy.get_param(self.namespace+'/autopilot/altStep')
		print self.altK.zSp
		self.home.x = self.bodK.x
		self.home.y = self.bodK.y
		# takeoff
		print abs(self.altK.zSp - self.altK.z) < 0.2
		while self.current_state == 'Takeoff' and not abs(self.altK.zSp - self.altK.z) < 0.2 and not rospy.is_shutdown():
			self.setp.header.stamp = rospy.Time.now()

			self.setp.velocity.z = self.altK.controller()
			(self.bodK.xSp, self.bodK.ySp) = autopilotLib.wayHome(self.bodK, self.home)
			(self.setp.velocity.x, self.setp.velocity.y, self.setp.yaw_rate) = self.bodK.controller()

			self.rate.sleep()
			self.command.publish(self.setp)
			# publish state topic
			self.state_topic.state = self.current_state
			self.state_topic.signal = self.current_signal
			self.state_pub.publish(self.state_topic)

			print 'State/Set/Alt/Gnd:', self.current_state, self.altK.zSp, self.altK.z, self.ZGROUND
			

		# Done with takoeff, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)
		
		self.debug()
	
		return

	######### Done with Takeof State #########

	# State: ObjectSearch
	def execute_objectSearch(self,way_points_tracker):
		self.current_state = 'ObjectSearch'
		self.current_signal= 'Running'

		self.debug()

		objectFound = False
		
		# execute some trajectory, e.g. circle
		# keep checking vision feedback
		# once an object is found, exit current state
		while  not objectFound and not rospy.is_shutdown():
			# TODO executing search trajectory
			if(way_points_tracker.index<len(way_points_list)):
				self.target_lat=way_points_tracker.way_points_list[way_points_tracker.index][0]
				self.target_lon=way_points_tracker.way_points_list[way_points_tracker.index][1]
				if((way_points_tracker.state="still")and(sqrt(pow(self.home.x-self.bodK.x,2)+pow(self.home.y-self.bodK.y,2))<1)):
					way_points_tracker.start = datetime.datetime.now()
					way_points_tracker.state="checking"
				if((way_points_tracker.state="checking"):
					way_points_tracker.stop = datetime.datetime.now()
					way_points_tracker.elapsed = way_points_tracker.stop - way_points_tracker.start
					if (datetime.timedelta(seconds=int(way_points_tracker.elapsed))>2);
					    way_points_tracker.state="reached"
				if((way_points_tracker.state="reached")
					way_points_tracker.index=way_points_tracker.index+1
					self.target_lat=way_points_tracker.way_points_list[way_points_tracker.index][0]
					self.target_lon=way_points_tracker.way_points_list[way_points_tracker.index][1]
					way_points_tracker.state="still"
					way_points_tracker.start=datetime.datetime.now()
					way_points_tracker.stop = way_points_tracker.start
					way_points_tracker.elapsed = way_points_tracker.stop - way_points_tracker.start
				
				(dy_enu, dx_enu) = self.LLA_local_deltaxy(self.current_lat, self.current_lon, self.target_lat, self.target_lon)
				self.home.x = self.bodK.x + dx_enu
				self.home.y = self.bodK.y + dy_enu
			else:
				way_points_tracker.index=0
			

			# check for objects
			objectFound, _ = self.monitorObjects()
	
			# publish control commands
			(self.bodK.xSp, self.bodK.ySp) = autopilotLib.wayHome(self.bodK, self.home)
			self.setp.velocity.z = self.altK.controller()
			(self.setp.velocity.x, self.setp.velocity.y, self.setp.yaw_rate) = self.bodK.controller()
	
			self.rate.sleep()
			# publish setpoint to pixhawk
			self.command.publish(self.setp)
			# publish state topic
			self.state_topic.state = self.current_state
			self.state_topic.signal = self.current_signal
			self.state_pub.publish(self.state_topic)
	
		# Done with searchobject state, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()

		return
	####### Done with ObjectSearch State #####

	# State: Picking
	def execute_picking(self):
		self.current_state = 'Picking'
		self.current_signal = 'Running'

		self.debug()

		# 1) track closest object, keep constant altitude
		# 2) once inside a pick envelope, descend, while tracking
		# 3) once below some LOW Alt, check pick state, keep tracking
		# 4) if low and picked, fly up, exit Picking state
		# 5) if low, and not picked, and timeout(maybe not?), fly up to search/track again goto(1)
		# !!!!!!!!!!!!!! Always make sure that you are in your assigned area!!!!!!!!!

		# temp variables
		objectFound = False
		xy=[0,0]
		picked = False

		# set altitude
		self.altK.zSp= self.ZGROUND + rospy.get_param(self.namespace+'/autopilot/altStep')

		# TODO: Activate gripper (write the ROS node for the gripper feedback/command)
		self.gripper_action.command = True
		self.gripper_pub.publish(self.gripper_action)

		while  self.current_signal != 'Failed' and not picked and not rospy.is_shutdown():
			objectFound, xy = self.monitorObjects()							# monitor objects
			if objectFound:										# found an object
				altCorrect = (self.altK.z - self.ZGROUND + self.CAMOFFSET)/rospy.get_param(self.namespace+'/pix2m/altCal')
				self.bodK.xSp = xy[0]*altCorrect
				self.bodK.ySp = xy[1]*altCorrect
				# for debug
				print 'XY setpoints: ', self.bodK.xSp, '/', self.bodK.ySp
				# this is a good observation, store it
				self.home.x = self.bodK.x       						# store most recent successful target
				self.home.y = self.bodK.y
				if self.inside_envelope(xy):
					self.altK.zSp = max(self.altK.z - 0.1*abs(self.altK.z), self.ZGROUND+self.PICK_ALT)	# descend if inside envelope
			else:											# object not found
				# if at max ALT (stil did not find objects), exit state with signal='Failed'
				if (self.altK.z >= self.ZGROUND+rospy.get_param(self.namespace+'/autopilot/altStep')):
					self.current_signal = 'Failed'

				(self.bodK.xSp, self.bodK.ySp) = autopilotLib.wayHome(self.bodK,self.home)	# go to last location where object was seen
				self.altK.zSp = min(self.altK.z + 0.1*abs(self.altK.z), self.ZGROUND+rospy.get_param(self.namespace+'/autopilot/altStep'))# increase altitude gradually, until an object is seen again

			# TODO !!!!!!!! constrain your location inside your zone!!!!!!

			# check if object is picked, fly up
			if (self.gripper_feedback.picked):
				picked = True	# set True to exit the while loop
				self.altK.zSp = self.ZGROUND + rospy.get_param(self.namespace+'/autopilot/altStep')
			
			self.setp.velocity.z = self.altK.controller()
			(self.setp.velocity.x, self.setp.velocity.y, self.setp.yaw_rate) = self.bodK.controller()
	
			self.rate.sleep()
			# publish setpoint to pixhawk
			self.command.publish(self.setp)
			# publish state topic
			self.state_topic.state = self.current_state
			self.state_topic.signal = self.current_signal
			self.state_pub.publish(self.state_topic)


		# Done with Picking state, send signal
		# Make sure the signal is not 'Failed', before declaring 'Done' signal
		if (self.current_signal != 'Failed'):
			self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)
		
		self.debug()

		return
				
					
	

	# State: GoToDrop
	def execute_gotodrop(self):
		self.current_state = 'Picking'
		self.current_signal = 'Running'

		self.debug()

		# temp variables
		arrived = False

		while not arrived and not rospy.is_shutdown():
			# TODO: convert the pre-drop location to local ENU (MAVROS expects ENU not NED)
			# (x_enu, y_enu) = self.get_enu_from_gps(self.DROP_COORDS)
			# self.home.x = x_enu
			# self.home.y = y_enu

			# TODO: implement trajectory to go to PRE_DROP zone
			if(ns="/Quad1"):
				(dy_enu, dx_enu) = self.LLA_local_deltaxy(self.current_lat, self.current_lon, self.areaBoundaries[8][0], self.areaBoundaries[8][1])
				self.home.x = self.bodK.x + dx_enu
				self.home.y = self.bodK.y + dy_enu 
			elif(ns="/Quad1"):
				(dy_enu, dx_enu) = self.LLA_local_deltaxy(self.current_lat, self.current_lon, self.areaBoundaries[10][0], self.areaBoundaries[10][1])
				self.home.x = self.bodK.x + dx_enu
				self.home.y = self.bodK.y + dy_enu
			elif(ns="/Quad1"):
				(dy_enu, dx_enu) = self.LLA_local_deltaxy(self.current_lat, self.current_lon, self.areaBoundaries[12][0], self.areaBoundaries[12][1])
				self.home.x = self.bodK.x + dx_enu
				self.home.y = self.bodK.y + dy_enu
			(self.bodK.xSp, self.bodK.ySp) = autopilotLib.wayHome(self.bodK, self.home)
			self.altK.zSp = self.ZGROUND + rospy.get_param(self.namespace+'/autopilot/altStep')

			# check if arrived
			if np.sqrt(self.bodK.xSp**2 + self.bodK.ySp*2) < 0.2:
				arrived = True	# set to True to leave the while loop

			# compute setpoints
			self.setp.velocity.z = self.altK.controller()
			(self.setp.velocity.x, self.setp.velocity.y, self.setp.yaw_rate) = self.bodK.controller()

			self.rate.sleep()
			# publish setpoints
			self.command.publish(setp)
			# publish state topic
			self.state_topic.state = self.current_state
			self.state_topic.signal = self.current_signal
			self.state_pub.publish(self.state_topic)

		# Done with GoToDrop state, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()

		return

	# State: WaitToDrop
	def execute_waittodrop(self):
		self.current_state='WaitToDrop'
		self.current_sginal='Running'

		self.debug()

		# TODO: Implement coordinated dropping below
		(dy_enu_other_1, dx_enu_other_1) = self.LLA_local_deltaxy(self.areaBoundaries[13][0], self.areaBoundaries[13][1], self.other_1_current_lat, self.other_1_current_lon)
		distance_other_1=sqrt(pow(dy_enu_other_1,2)+pow(dx_enu_other_1,2))
		(dy_enu_other_2, dx_enu_other_2) = self.LLA_local_deltaxy(self.areaBoundaries[13][0], self.areaBoundaries[13][1], self.other_2_current_lat, self.other_2_current_lon)
		distance_other_2=sqrt(pow(dy_enu_other_2,2)+pow(dx_enu_other_2,2))

		if(ns="/Quad1"):
			if (not(self.other_1_state="Dropping") and  not(self.other_2_state="Dropping") and (distance_other_1>6) and (distance_other_2>6)):
				self.current_signal = 'Done'


		elif(ns="/Quad2"):
			if (not(self.other_1_state="WaitToDrop") and not(self.other_1_state="Dropping") and not(self.other_2_state="Dropping") and (distance_other_1>6) and (distance_other_2>6)):
				self.current_signal = 'Done'

		elif(ns="/Quad3"):
			if (not(self.other_1_state="WaitToDrop") and not(self.other_1_state="Dropping") and not(self.other_2_state="WaitToDrop") and not(self.other_2_state="Dropping") and (distance_other_1>6) and (distance_other_2>6)):
				self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()
	
		return

	# State: Drop
	def execute_drop(self):
		self.current_state='Dropping'
		self.current_sginal='Running'

		self.debug()

		# TODO: look for dropbox (vision-based)
		# once centerd, go to drop alt
		# deactivate magnets, and keep checking gripper feedback!


		# Done with Drop state, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()

		return

	# State: GoHome
	def execute_gohome(self):
		self.current_state='GoHome'
		self.current_signal='Running'

		self.debug()

		# go to the Home XY coordinates. Landing is handled by landing state, see below.

		# Done with GoHome state, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()

		return

	# State: Land
	def execute_land(self):
		self.current_state='Land'
		self.current_signal='Running'

		self.debug()

		# send land command to Pixhawk, or execute landing routine using the velocity controller

		# Done with GoHome state, send signal
		self.current_signal = 'Done'
		# publish state topic
		self.state_topic.state = self.current_state
		self.state_topic.signal = self.current_signal
		self.state_pub.publish(self.state_topic)

		self.debug()

		return

	#                                          (End of States Implementation)                                                                #
	#----------------------------------------------------------------------------------------------------------------------------------------#

	#----------------------------------------------------------------------------------------------------------------------------------------#
	#                                          (State Transition Function)	                                                                 #
	def update_state(self):
		
		# States: {Idle, Takeoff, ObjectSearch, Picking, GoToDrop, WaitToDrop, Dropping, GoHome, Land}
		# Possible Signals for each state:
		#	Takeoff:	{'Done', 'Running'}
		#	ObjectSearch:	{'Done', 'Running'}
		#	Picking:	{'Done', 'Running', 'Failed'}
		#	GoToDrop:	{'Done', 'Running'}
		#	Dropping:	{'Done', 'Running'}
		#	GoHome:		{'Done', 'Running'}
		#	Land:		{'Done', 'Running'}
		# manage the transition between states
		state = self.current_state
		signal = self.current_signal
		if (state == 'Start' and signal != 'Ready' and self.START_SIGNAL):	# initial signal
			self.execute_start()
		elif (state == 'Start' and signal == 'Ready'):	# Done: start -> go to: Takeoff state
			self.execute_takeoff()
		elif (state == 'Takeoff' and signal == 'Done'):	# Done: Takeoff -> go to: ObjectSearch state
			self.execute_objectSearch()
		elif (state == 'ObjectSearch' and signal == 'Done'): # Done: ObjectSearch -> go to: Picking state
			self.execute_picking()
		elif (state == 'Picking'):			# Two cases: 
			if (signal == 'Failed'):			# Failed -> go to: ObjectSearch state
				self.execute_objectSearch()	
			if (signal == 'Done'):				# Done: Picking -> go to: GoToDrop state
				self.execute_gotodrop()
		elif (state == 'GoToDrop' and signal == 'Done'):	# Done: GoToDrop -> go to: WiatToDrop state
			self.execute_wiattodrop()
		elif (state == 'WaitToDrop' and signal == 'Done'):# Done: WaitToDrop -> go to: Drop state
			self.execute_drop()
		elif (state == 'Drop' and signal == 'Done'):	# Done: Drop -> go back to: ObjectSearch state
			self.execute_objectSearch()

	#                                          (End of transition function)                                                                  #
	#----------------------------------------------------------------------------------------------------------------------------------------#


	#----------------------------------------------------------------------------------------------------------------------------------------#
	#                                               (helper functions)                                                                       #

	# check if a colored object is found
	# returns a tuple: (bool objectFound, xy_coord of closest object)
	def monitorObjects(self):
		# define distance to each color object
		d_to_blue=np.inf
		d_to_green=np.inf

		# radius list: of detected objects
		r_list=[]
		# list of x/y coords of found objects
		xy_list=[]
	
		# flag if object is found
		objectFound = False

		# update the distance if (blue) is found
		if self.blue_target.z > 0 :
			d_to_blue = np.sqrt(self.blue_target.x**2 + self.blue_target.y**2)
			r_list.append(d_to_blue)
			xy_list.append([self.blue_target.x, self.blue_target.y])
			objectFound = True

		# update the distance if (green) is found
		if self.green_target.z > 0 :
			d_to_green = np.sqrt(self.green_target.x**2 + self.green_target.y**2)
			r_list.append(d_to_green)
			xy_list.append([self.green_target.x, self.green_target.y])
			objectFound = True			

		# other colors..........?

		# find the closest object
		if len(r_list) > 0:
			min_d_index = r_list.index(min(r_list))
			# Finally return
			return (objectFound, xy_list[min_d_index])
		else:
			return (objectFound, [])
	
		
	########## End of Monitoring Objects #######################

	# determins if an object is inside an allowable descend envelope
	def inside_envelope(self,xy):
		# currently, only based on relative pos
		if np.sqrt(xy[0]**2 + xy[1]**2) <= self.ENVELOPE_XY_POS:
			return True
		else:
			return False
	############## End of envelope function #################

	######## for debug: prints the state/signal
	def debug(self):
		if self.DEBUG:
			print '#--------------------------------------#'
			print 'State/Signal: ', self.current_state, ' -> ', self.current_signal
			print '#--------------------------------------#'
			
			if rospy.is_shutdown():
				print '|------ ROS IS SHUTTING DOWN------|'
	############### End of debug function ##################
	######## for intermediate points along a great circle path:########################

		#The function takes two coordinate pairs and a user-specified number of segments. 
		#It yields a set of intermediate points along a great circle path. 
		#def tweensegs(longitude1,latitude1,longitude2,latitude2,num_of_segments):

	def intermediate(self,llaPointStart,llaPointEnd,num_of_segments):

		ptlon1 = llaPointStart[1]
		ptlat1 = llaPointStart[0]
		ptlon2 = llaPointEnd[1]
		ptlat2 = llaPointEnd[0]

		numberofsegments = num_of_segments
		onelessthansegments = numberofsegments - 1
		fractionalincrement = (1.0/onelessthansegments)

		ptlon1_radians = math.radians(ptlon1)
		ptlat1_radians = math.radians(ptlat1)
		ptlon2_radians = math.radians(ptlon2)
		ptlat2_radians = math.radians(ptlat2)

		distance_radians=2*math.asin(math.sqrt(math.pow((math.sin((ptlat1_radians-ptlat2_radians)/2)),2) + math.cos(ptlat1_radians)*math.cos(ptlat2_radians)*math.pow((math.sin((ptlon1_radians-ptlon2_radians)/2)),2)))
		# 6371.009 represents the mean radius of the earth
		# shortest path distance
		distance_km = 6371.009 * distance_radians

		mylats = []
		mylons = []

		# write the starting coordinates
		mylats.append([])
		mylons.append([])
		mylats[0] = ptlat1
		mylons[0] = ptlon1 

		f = fractionalincrement
		icounter = 1
		while (icounter <  onelessthansegments):
			icountmin1 = icounter - 1
			mylats.append([])
			mylons.append([])
			# f is expressed as a fraction along the route from point 1 to point 2
			A=math.sin((1-f)*distance_radians)/math.sin(distance_radians)
			B=math.sin(f*distance_radians)/math.sin(distance_radians)
			x = A*math.cos(ptlat1_radians)*math.cos(ptlon1_radians) + B*math.cos(ptlat2_radians)*math.cos(ptlon2_radians)
			y = A*math.cos(ptlat1_radians)*math.sin(ptlon1_radians) +  B*math.cos(ptlat2_radians)*math.sin(ptlon2_radians)
			z = A*math.sin(ptlat1_radians) + B*math.sin(ptlat2_radians)
			newlat=math.atan2(z,math.sqrt(math.pow(x,2)+math.pow(y,2)))
			newlon=math.atan2(y,x)
			newlat_degrees = math.degrees(newlat)
			newlon_degrees = math.degrees(newlon)
			mylats[icounter] = newlat_degrees
			mylons[icounter] = newlon_degrees
			icounter += 1
			f = f + fractionalincrement

		# write the ending coordinates
		mylats.append([])
		mylons.append([])
		mylats[onelessthansegments] = ptlat2
		mylons[onelessthansegments] = ptlon2
		listOfPoints=[]
		for i in range(0,len(mylats)):
			listOfPoints.append((mylats[i],mylons[i]))
		return listOfPoints

		# Now, the array mylats[] and mylons[] have the coordinate pairs for intermediate points along the geodesic
		# My mylat[0],mylat[0] and mylat[num_of_segments-1],mylat[num_of_segments-1] are the geodesic end point
        ############### End of intermediate function ##################
        

    ######## function for defining the field boundqries :########################
	
	def path(ns,areaBoundaries,cameraView):
		dividerUnity=min(cameraView,5)
		if (ns=="/Quad1"):

			num_of_segments_up_1=int(7/dividerUnity)
			upperBoundaries_1=intermediate(self,areaBoundaries[1],areaBoundaries[0],num_of_segments_up_1)
			num_of_segments_up_2=int(18/dividerUnity)
			upperBoundaries_2=intermediate(self,areaBoundaries[0],areaBoundaries[7],num_of_segments_up_2)
			num_of_segments_up_3=int(5/dividerUnity)
			upperBoundaries_3=intermediate(self,areaBoundaries[8],areaBoundaries[9],num_of_segments_up_3)
			num_of_segments_down=num_of_segments_up_1+num_of_segments_up_2+num_of_segments_up_3
			downBoundaries=intermediate(self,areaBoundaries[2],areaBoundaries[3],num_of_segments_down)

			upperBoundaries=upperBoundaries_1
			upperBoundaries.append(upperBoundaries_2)
			upperBoundaries.append(upperBoundaries_3)

			way_point_list=[]
			for i in range(0,len(downBoundaries)-1):
				way_points_list.append(downBoundaries[i])
				way_points_list.append(upperBoundaries[i])
		if (ns=="/Quad2"):

			num_of_segments_up_3=int(7/dividerUnity)
			upperBoundaries_3=intermediate(self,areaBoundaries[6],areaBoundaries[5],num_of_segments_up_3)
			num_of_segments_up_2=int(18/dividerUnity)
			upperBoundaries_2=intermediate(self,areaBoundaries[11],areaBoundaries[6],num_of_segments_up_2)
			num_of_segments_up_1=int(5/dividerUnity)
			upperBoundaries_1=intermediate(self,areaBoundaries[9],areaBoundaries[10],num_of_segments_up_1)
			num_of_segments_down=num_of_segments_up_1+num_of_segments_up_2+num_of_segments_up_3
			downBoundaries=intermediate(self,areaBoundaries[3],areaBoundaries[4],num_of_segments_down)

			upperBoundaries=upperBoundaries_1
			upperBoundaries.append(upperBoundaries_2)
			upperBoundaries.append(upperBoundaries_3)

			way_points_list=[]
			for i in range(0,len(downBoundaries)-1):
				way_points_list.append(downBoundaries[i])
				way_points_list.append(upperBoundaries[i])

		if (ns=="/Quad3"):

			num_of_segments=int(46/dividerUnity)

			upperBoundaries=intermediate(self,areaBoundaries[0],areaBoundaries[6],num_of_segments)
		
			downBoundaries=intermediate(self,areaBoundaries[7],areaBoundaries[11],num_of_segments)

			way_points_list=[]
			for i in range(0,len(downBoundaries)-1):
				way_points_list.append(downBoundaries[i])
				way_points_list.append(upperBoundaries[i])


		return(way_points_list)

    ######## function for converting LLA points to local xy(NED) :########################

	def LLA_local_deltaxy(self, lat_0, lon_0,  lat,  lon):

		M_DEG_TO_RAD = 0.01745329251994
		CONSTANTS_RADIUS_OF_EARTH	= 6371000.0
		DBL_EPSILON = 2.2204460492503131E-16

		curr_lat_rad = lat_0 * M_DEG_TO_RAD
		curr_lon_rad = lon_0 * M_DEG_TO_RAD
		curr_sin_lat = sin(curr_lat_rad)
		curr_cos_lat = cos(curr_lat_rad)

		lat_rad = lat * M_DEG_TO_RAD
		lon_rad = lon * M_DEG_TO_RAD

		sin_lat = sin(lat_rad)
		cos_lat = cos(lat_rad)

		cos_d_lon = cos(lon_rad - curr_lon_rad)

		arg = curr_sin_lat * sin_lat + curr_cos_lat * cos_lat * cos_d_lon

		if (arg > 1.0):
			arg = 1.0
		elif (arg < -1.0):
			arg = -1.0

		c = acos(arg)

		if(abs(c) < DBL_EPSILON):
			k=1
		else:
			k=c/sin(c)


		delta_x = k * (curr_cos_lat * sin_lat - curr_sin_lat * cos_lat * cos_d_lon) * CONSTANTS_RADIUS_OF_EARTH
		delta_y = k * cos_lat * sin(lon_rad - curr_lon_rad) * CONSTANTS_RADIUS_OF_EARTH
		return (delta_x,delta_y)

	############### End of LLA_local_deltaxy function ##################
	#                                           (End of helper functions)                                                                    #
	#----------------------------------------------------------------------------------------------------------------------------------------#


	#----------------------------------------------------------------------------------------------------------------------------------------#
	#                                                 (Callbacks)                                                                            #

	############ Gripper callback function #####################
	def gripper_cb(self,msg):
		if msg is not None:
			self.gripper_feedback.picked = msg.picked
	########### End of Gripper callback function ##############

	#################### MAVROS GPS Callback #################
	def gps_cb(self, msg):
		if msg is not None:
			self.current_lat = msg.latitude
			self.current_lon = msg.longitude
	################## End of GPS callback ##################

	#################### MAVROS other GPS Callback #################
	def gps_other_1_cb(self, msg):
		if msg is not None:
			self.other_1_current_lat = msg.latitude
			self.other_1_current_lon = msg.longitude

	def gps_other_2_cb(self, msg):
		if msg is not None:
			self.other_2_current_lat = msg.latitude
			self.other_2_current_lon = msg.longitude
	################## End of other GPS callback ##################
	#################### MAVROS others states Callback #################
	def state_other_1_cb(self, msg):
		if msg is not None:
			self.other_1_state = msg.state

	def state_other_2_cb(self, msg):
		if msg is not None:
			self.other_2_state = msg.state
	################## End of other others states callback ##################

	#                                              (End of Callbacks)                                                                        #
	#----------------------------------------------------------------------------------------------------------------------------------------#	
		
#############################################
def mission():
	rospy.init_node('mission1', anonymous=True)

	# get namespace
	ns=rospy.get_namespace()
	ns=''
	sm = StateMachineC(ns)
	sm.DEBUG=True
	sm.current_state='Start'
	sm.START_SIGNAL=True
	sm.target_lat = 47.3978434
	sm.target_lon = 8.5432450
	
	sm.cameraView=1;
	sm.areaBoundaries= ##
	sm.way_points_list=path(ns,sm.areaBoundaries,sm.cameraView)
	while not rospy.is_shutdown():
		sm.update_state()
	

######### Main ##################
if __name__ == '__main__':
    try:
        mission()
    except rospy.ROSInterruptException:
        pass
