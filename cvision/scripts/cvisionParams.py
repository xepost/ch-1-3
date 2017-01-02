#####
#
# cvisionParams.py
#
#####

import rospy

def setParams():

    # ROS parameters for getLaunchPadx3
    rospy.set_param('/getLaunchPad/feCamera', True)              # use fisheye mask and processing
    rospy.set_param('/getLaunchPad/camFlip', True)               # camera rotated 180deg
    rospy.set_param('/getLaunchPad/pxMasking', True)             # use proximity masking
    rospy.set_param('/getLaunchPad/centroidThresh', 10000.0)     # threshold for centroid detection
    rospy.set_param('/getLaunchPad/circleTol', 1.5)              # radius multiplier for circles
    rospy.set_param('/getLaunchPad/erodeOn', False)              # use erode/dilate vs blur
    rospy.set_param('/getLaunchPad/liberal', False)              # allow lone bright white detection
    rospy.set_param('/getLaunchPad/reduction', 2)                # image reduction for realtime
    rospy.set_param('/getLaunchPad/loopRate', 15)                # publishing rate (hz)
    
    rospy.set_param('/getLaunchPad/imgShow', True)               # show images to screen
    rospy.set_param('/getLaunchPad/imgPub', False)               # publish raw images
    rospy.set_param('/getLaunchPad/imgPubRate', 3)               # publishing rate
    rospy.set_param('/getLaunchPad/imgStream', False)             # stream reduced images
    rospy.set_param('/getLaunchPad/imgStreamRate', 2)            # streaming rate
    
    rospy.set_param('/getLaunchPad/hoverLow', False)             # corner override (temp)
    
    # ROS parameters for pix2m
    rospy.set_param('/pix2m/LX', 640.0)                     # full size screen width
    rospy.set_param('/pix2m/LY', 480.0)                     # full size screen height
    rospy.set_param('/pix2m/altCal',1.2)                    # calibration altitude
    rospy.set_param('/pix2m/m2pix', 0.00104167)             # 0.5m = 480pixels



 
