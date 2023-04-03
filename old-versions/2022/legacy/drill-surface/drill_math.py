import math

def mean(array):
    return sum(array) / len(array)

def dot_product(vec_1, vec_2):
    return sum([vec_1[i]*vec_2[i] for i in range(3)])

def vector_length(vec):
    return math.sqrt(dot_product(vec,vec))

def vector_projection(projected,target):
    prefactor = dot_product(projected, target)/vector_length(target)**2
    proj = [prefactor*target[i] for i in range(3)]
    return proj

def vector_difference(vec_1,vec_2):
    return [vec_1[i] - vec_2[i] for i in range(3)]

def vector_angle(vec_1,vec_2):
    return math.acos(dot_product(vec_1,vec_2)/(vector_length(vec_1)*vector_length(vec_2)))

def rad2deg(x):
    return 180*x/math.pi


def rotate(coord, origin, angle):

    x = float(coord[0]) - float(origin[0])
    y = float(coord[1]) - float(origin[1])

    x_ = math.cos(angle)*x + math.sin(angle)*y + float(origin[0])
    y_ = -math.sin(angle)*x + math.cos(angle)*y + float(origin[1])

    return (x_,y_)

def sec2hms(sec):
    sec = round(sec,0)
    s=sec%60
    m=math.floor(sec/60)
    h = math.floor(m/60)
    m = m-60*h

    if h < 1:
        return ('{:02.0f}'.format(m) +':'+ '{:02.0f}'.format(s))
    else:
        return ('{:02.0f}'.format(h) +':'+ '{:02.0f}'.format(m) +':'+ '{:02.0f}'.format(s))
