import matplotlib.pyplot as plt   

def plot(base_pos, platform_pos, platform_mid_height, PLATFORM_NAME ):
    base_labels = ['base{0}'.format(i) for i in range(6)]
    platform_labels = ['platform{0}'.format(i) for i in range(6)]
    if PLATFORM_NAME == "Flying Platform":
       img = plt.imread("flying_platform.png")
       plt.imshow(img, zorder=1, extent=[-600, 600, -600, 600])
    else:
        img = plt.imread("chair_red.png")
        plt.imshow(img, zorder=1, extent=[-400, 400, -400, 400])
        
    bx= base_pos[:,0]
    by = base_pos[:,1]
    plt.scatter(bx,by,zorder=2)
    
    px= platform_pos[:,0]
    py = platform_pos[:,1]
    plt.axis('equal')
    plt.scatter(px,py,zorder=3)
    # plt.imshow(img, zorder=0, extent=[-100, 100, -100, 100])

    plt.xlabel('X axis mm')
    plt.ylabel('Y axis mm')
    plt.axhline(0, color='gray')
    plt.axvline(0, color='gray')
    plt.title(PLATFORM_NAME)
    if PLATFORM_NAME == "Flying Platform":
        lbl_xoffset = 20
        lbl_yoffset = 20
    else:
         lbl_xoffset = 20
         lbl_yoffset = 20

    for label, x, y in zip(base_labels, bx, by):
        if x > 0 and y < 0:
           h = 'right'
        else:
           h = 'left'
        plt.annotate(
            label,
            xy=(x, y), xytext=(lbl_xoffset, lbl_yoffset),
            textcoords='offset points', ha=h, va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle = '->', connectionstyle='arc3,rad=0'))
    for label, x, y in zip(platform_labels, px, py):
        if x < 0 and y < 0:
           h = 'left'
        else:
           h = 'right'
        plt.annotate(
            label,
            xy=(x, y), xytext=(-20, 20),
            textcoords='offset points', ha=h, va='bottom',
            bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.5),
            arrowprops=dict(arrowstyle = '->', connectionstyle='arc3,rad=0'))

    plt.show()
