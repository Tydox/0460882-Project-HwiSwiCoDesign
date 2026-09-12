"""
This file contains definitions for a simple raytracer.
Copyright Callum and Tony Garnock-Jones, 2008.

This file may be freely redistributed under the MIT license,
http://www.opensource.org/licenses/mit-license.php

From http://www.lshift.net/blog/2008/10/29/toy-raytracer-in-python
"""

import array
import math
import os

# Keep numeric libraries on one thread, including fresh pyperf worker imports.
for _thread_setting in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                        "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_thread_setting] = "1"
import numpy as np
import pyperf


DEFAULT_WIDTH = 100 #100
DEFAULT_HEIGHT = 100 #100
DEFAULT_BATCH_SIZE = 256
EPSILON = 0.00001


class Vector(object):

    __slots__ = ('x', 'y', 'z') #avoiding circular references and memory overhead of __dict__ and __weakref__ for each instance of the class. This is a memory optimization.

    def __init__(self, initx, inity, initz): 
        self.x = initx
        self.y = inity
        self.z = initz

    def __str__(self): # this methis is used for printing the data of the class. its used when you call print() on an instance of the class. It returns a string representation of the object.
        return '(%s,%s,%s)' % (self.x, self.y, self.z) #print example is (1,2,3) for Vector(1,2,3) we use % formatting to create the string representation of the vector's coordinates.

    def __repr__(self):# we use this for debugging and development purposes. It returns a string that, when evaluated, would recreate the object. In this case, it returns a string in the format 'Vector(x,y,z)' where x, y, and z are the coordinates of the vector.
        return 'Vector(%s,%s,%s)' % (self.x, self.y, self.z) #example %s for string and replaced by value of self.x. the mod operator does the formatting. The % operator is used to format the string by replacing the placeholders with the actual values of the vector's coordinates.

    def magnitude(self):
        return math.sqrt(self.dot(self))#math equation is: magnitude = sqrt(x^2 + y^2 + z^2) 

    def __add__(self, other):#overloading the + operator for vector addition.
        if other.isPoint():# It takes another vector or point as an argument and returns a new vector or point that is the result of adding the two together.
            return Point(self.x + other.x, self.y + other.y, self.z + other.z)
        else:
            return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):#overloading the - operator for vector subtraction. 
        other.mustBeVector()#makes sure that the other object is a vector. If it is not, it raises an exception. This is important because you cannot subtract a point from a vector in this context.
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)#It takes another vector as an argument and returns a new vector that is the result of subtracting the other vector from this one.

    def scale(self, factor):#not using __rmul__ or __rmul__ because we want to be able to multiply a vector by a scalar (a single number). https://docs.python.org/3/reference/datamodel.html#object.__radd__
        return Vector(factor * self.x, factor * self.y, factor * self.z)

    def dot(self, other):#creating new operator for dot product of two vectors. SIMD instructions can be used to speed up the dot product calculation, which is a common operation in graphics and physics simulations. The dot product is used to calculate angles between vectors, projections, and lighting calculations in ray tracing.
        other.mustBeVector() 
        return (self.x * other.x) + (self.y * other.y) + (self.z * other.z)

    def cross(self, other):#create new operator for cross product of two vectors. The cross product is used to calculate normals to surfaces, which are important for lighting calculations in ray tracing.
        other.mustBeVector()
        return Vector(self.y * other.z - self.z * other.y,
                      self.z * other.x - self.x * other.z,
                      self.x * other.y - self.y * other.x) #Check if we can use SIMD to speed up

    def normalized(self): #this method returns a new vector that has the same direction as the original vector but with a magnitude of 1.
        x = self.x
        y = self.y
        z = self.z
        # Preserve the dot-product order and reciprocal-then-multiply rounding.
        factor = 1.0 / math.sqrt((x * x) + (y * y) + (z * z))
        return Vector(factor * x, factor * y, factor * z)

    def negated(self):#retruns same vector but with opposite direction. 
        return self.scale(-1)

    def __eq__(self, other):#overloading the == operator for vector equality. This method checks if two vectors are equal by comparing their x, y, and z coordinates. If all three coordinates are equal, the method returns True; otherwise, it returns False.
        return (self.x == other.x) and (self.y == other.y) and (self.z == other.z)

    def isVector(self):#new method to check if the object is a vector. This is useful for type checking in other methods, ensuring that operations are performed on the correct types of objects.
        return True

    def isPoint(self):#method to check if the object is a point. This is useful for type checking in other methods, ensuring that operations are performed on the correct types of objects.
        return False

    def mustBeVector(self):#how it returns true or false? point and vector classes have oppisite return values for isVector and isPoint. If the object is a vector, mustBeVector returns self; if it is a point, it raises an exception. This is used to enforce type safety in operations that require a vector.
        return self

    def mustBePoint(self):#used with point objects to ensure that the object is indeed a point. If the object is a point, mustBePoint returns self; if it is a vector, it raises an exception. This is used to enforce type safety in operations that require a point.
        raise 'Vectors are not points!'

    def reflectThrough(self, normal): #calculates the reflection of the vector through a given normal vector. first scales the normal vector by the dot product of the original vector and the normal, then subtracts twice this scaled normal from the original vector to get the reflected vector.
        projection = self.dot(normal)
        # Keep both scaling steps in their original order without temporary vectors.
        return Vector(self.x - 2 * (projection * normal.x),
                      self.y - 2 * (projection * normal.y),
                      self.z - 2 * (projection * normal.z))

#we do this to avoid creating new Vector objects for these common vectors, which can save memory and improve performance in a raytracer where these vectors are used frequently.
#we make the following: zero vector, right vector, up vector, and out vector. These are commonly used in graphics programming for various calculations, such as defining directions and orientations in 3D space.
#so to save memory and improve performance, we create these vectors once and reuse them throughout the program instead of creating new instances every time they are needed.
#they are global constants that can be accessed anywhere in the code without needing to create new instances of the Vector class. This is especially useful in a raytracer, where performance and memory usage are critical.
#they arent really constants because they can be modified, but by convention, they are treated as constants and should not be changed. This is a common practice in programming to indicate that certain values are intended to remain unchanged throughout the program.
Vector.ZERO = Vector(0, 0, 0)
Vector.RIGHT = Vector(1, 0, 0)
Vector.UP = Vector(0, 1, 0)
Vector.OUT = Vector(0, 0, 1)
#this is a test to check if the reflectThrough method is working correctly. It reflects the RIGHT vector through the UP vector and checks if the result is still the RIGHT vector. This is a basic test to ensure that the reflection calculation is functioning as expected.
assert Vector.RIGHT.reflectThrough(Vector.UP) == Vector.RIGHT
#this is a test to check if the reflectThrough method is working correctly. It reflects the vector (-1, -1, 0) through the UP vector and checks if the result is (-1, 1, 0). This is a basic test to ensure that the reflection calculation is functioning as expected.
#because it should move up to the positive y direction while keeping the x and z coordinates the same.
assert Vector(-1, -1, 0).reflectThrough(Vector.UP) == Vector(-1, 1, 0)


class Point(object):

    __slots__ = ('x', 'y', 'z')#slots gives us like c struct memory layout for the class. It avoids the overhead of a dictionary for each instance, which can save memory and improve performance, especially when creating many instances of the class.

    def __init__(self, initx, inity, initz):
        self.x = initx
        self.y = inity
        self.z = initz

    def __str__(self): #overloading the str() function for Point objects. This method returns a string representation of the point in the format "(x,y,z)", where x, y, and z are the coordinates of the point. This is useful for printing and debugging purposes.
        return '(%s,%s,%s)' % (self.x, self.y, self.z)

    def __repr__(self):#overloading the repr() function for Point objects. This method returns a string representation of the point in the format "Point(x,y,z)", where x, y, and z are the coordinates of the point. This is useful for debugging and development purposes, as it provides a clear and unambiguous representation of the point object.
        return 'Point(%s,%s,%s)' % (self.x, self.y, self.z)

    def __add__(self, other):#overloading the + operator for Point objects. This method allows you to add a vector to a point, resulting in a new point that is translated by the vector. It first checks if the other object is a vector using the mustBeVector() method, which raises an exception if it is not. If the other object is a vector, it returns a new Point object with coordinates that are the sum of the point's coordinates and the vector's coordinates.
        other.mustBeVector()
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):#overloading the - operator for Point objects. This method allows you to subtract a point from another point, resulting in a vector that represents the direction and distance from the other point to this point. It first checks if the other object is a point using the isPoint() method. If it is, it returns a new Vector object with coordinates that are the difference between this point's coordinates and the other point's coordinates. If the other object is not a point (i.e., it is a vector), it returns a new Point object that is translated by the negative of the vector's coordinates.
        if other.isPoint():
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
        else:
            return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def isVector(self):
        return False

    def isPoint(self):
        return True

    def mustBeVector(self):
        raise 'Points are not vectors!'

    def mustBePoint(self):
        return self

#we use Shpere(object) and not Sphere() but its the same thing. The object is the base class for all classes in Python. by default, all classes inherit from object, so explicitly specifying it is not necessary. However, it can be done for clarity or to maintain compatibility with older versions of Python that do not support new-style classes.
class Sphere(object):#this class represents a sphere in 3D space. It has a center point and a radius. The class provides methods to calculate the intersection of a ray with the sphere and to get the normal vector at a point on the sphere's surface.

    def __init__(self, centre, radius):
        centre.mustBePoint()
        self.centre = centre
        self.radius = radius
        # Sphere radii stay constant throughout this benchmark's scene.
        self.radiusSquared = radius * radius

    def __repr__(self):
        return 'Sphere(%s,%s)' % (repr(self.centre), self.radius)

    def intersectionTime(self, ray): #the equation is (t - c) · d = r and the discriminant is r^2 - (c - p)^2 + ((c - p) · d)^2. If the discriminant is negative, there is no intersection. If it is zero or positive, the intersection time can be calculated as v - sqrt(discriminant), where v = (c - p) · d.

        #the function calculates the following equations:
        #  1. Vector from the ray's origin to the sphere's center: C - P 
        # 2. Projection of this vector onto the ray's direction: v = (C - P) .dot(D) 
        # 3. Squared distance from the sphere's center to the ray: cp = (C - P) .dot(C - P) 
        # 4. Discriminant for intersection: discriminant = r^2 - (cp - v^2) If the discriminant is negative, there is no intersection. 
        # If it is non-negative, the intersection time is given by: t = v - sqrt(discriminant)
        
        centre = self.centre
        point = ray.point
        direction = ray.vector
        cpx = centre.x - point.x
        cpy = centre.y - point.y
        cpz = centre.z - point.z
        # Keep the dot products' original left-to-right arithmetic order.
        v = (cpx * direction.x) + (cpy * direction.y) + (cpz * direction.z)
        cpSquared = (cpx * cpx) + (cpy * cpy) + (cpz * cpz)
        discriminant = self.radiusSquared - (cpSquared - v * v)
        if discriminant < 0:
            return None
        else:
            return v - math.sqrt(discriminant)

    def normalAt(self, p):
        centre = self.centre
        x = p.x - centre.x
        y = p.y - centre.y
        z = p.z - centre.z
        factor = 1.0 / math.sqrt((x * x) + (y * y) + (z * z))
        return Vector(factor * x, factor * y, factor * z)


class Halfspace(object): #a half space is a region of space that is divided by a plane, visually it looks like a flat surface that extends infinitely in all directions. The half space is defined by a point on the plane and a normal vector that is perpendicular to the plane. The normal vector points towards the "inside" of the half space, indicating which side of the plane is considered to be part of the half space.
#hyperplane vs halfspace is that a hyperplane is a flat, n-1 dimensional subspace that divides an n-dimensional space into two half spaces. A half space is one of the two regions created by a hyperplane. In 3D space, a hyperplane is a plane, and the two half spaces are the regions on either side of the plane. In 2D space, a hyperplane is a line, and the two half spaces are the regions on either side of the line.
    def __init__(self, point, normal):
        self.point = point
        self.normal = normal.normalized()

    def __repr__(self):
        return 'Halfspace(%s,%s)' % (repr(self.point), repr(self.normal))

    def intersectionTime(self, ray):#equations is (p - p0) · n / (d · n) where p is the ray's origin, p0 is a point on the plane, d is the ray's direction, and n is the plane's normal vector. If d · n is zero, the ray is parallel to the plane and there is no intersection.
        v = ray.vector.dot(self.normal)
        if v:
            return 1 / -v
        else:
            return None

    def normalAt(self, p):#eq is n = (p - p0) / ||p - p0|| where p is the point on the surface, p0 is a point on the plane, and n is the normal vector. Since the normal vector is constant for a half space, we can simply return the normalized normal vector that was provided when the half space was created.
        return self.normal #but we turn normal and not n = (p - p0) / ||p - p0|| because its not needed because the normal vector is constant for a half space, meaning it does not change based on the point p. The normal vector is defined by the orientation of the half space and remains the same regardless of where you are on the surface. Therefore, we can simply return the normalized normal vector that was provided when the half space was created, without needing to calculate it based on the point p.


class Ray(object):

    __slots__ = ('point', 'vector')

    def __init__(self, point, vector):
        self.point = point
        self.vector = vector.normalized()

    def __repr__(self):
        return 'Ray(%s,%s)' % (repr(self.point), repr(self.vector))

    def pointAtTime(self, t):
        # Pnew=Pold+d*T: calculate the point without a temporary scaled vector.
        point = self.point
        vector = self.vector
        return Point(point.x + t * vector.x,
                     point.y + t * vector.y,
                     point.z + t * vector.z)


Point.ZERO = Point(0, 0, 0)


class Canvas(object):

    def __init__(self, width, height):
        self.bytes = array.array('B', [0] * (width * height * 3))
        for i in range(width * height):
            self.bytes[i * 3 + 2] = 255
        self.width = width
        self.height = height

    def plot(self, x, y, r, g, b):
        i = ((self.height - y - 1) * self.width + x) * 3
        self.bytes[i] = max(0, min(255, int(r * 255)))
        self.bytes[i + 1] = max(0, min(255, int(g * 255)))
        self.bytes[i + 2] = max(0, min(255, int(b * 255)))

    def write_ppm(self, filename):
        header = 'P6 %d %d 255\n' % (self.width, self.height)
        with open(filename, "wb") as fp:
            fp.write(header.encode('ascii'))
            fp.write(self.bytes.tobytes())


def firstIntersection(intersections):
    result = None
    for i in intersections:
        candidateT = i[1]
        if candidateT is not None and candidateT > -EPSILON:
            if result is None or candidateT < result[1]:
                result = i
    return result


class Scene(object):

    def __init__(self):
        self.objects = []
        self.lightPoints = []
        self.position = Point(0, 1.8, 10)
        self.lookingAt = Point.ZERO
        self.fieldOfView = 45
        self.recursionDepth = 0

    def moveTo(self, p):
        self.position = p

    def lookAt(self, p):
        self.lookingAt = p

    def addObject(self, object, surface):
        self.objects.append((object, surface))

    def addLight(self, p):
        self.lightPoints.append(p)

    def render(self, canvas, batch_size=DEFAULT_BATCH_SIZE):
        BatchedRenderer(self).render(canvas, batch_size)

    def rayColour(self, ray):
        if self.recursionDepth > 3:
            return (0, 0, 0)
        try:
            self.recursionDepth = self.recursionDepth + 1
            closestTime = None
            for o, s in self.objects:
                t = o.intersectionTime(ray)
                if t is not None and t > -EPSILON:
                    # Strict comparison retains the first object on a tie.
                    if closestTime is None or t < closestTime:
                        closestObject = o
                        closestTime = t
                        closestSurface = s
            if closestTime is None:
                return (0, 0, 0)  # the background colour
            else:
                p = ray.pointAtTime(closestTime)
                return closestSurface.colourAt(
                    self, ray, p, closestObject.normalAt(p))
        finally:
            self.recursionDepth = self.recursionDepth - 1

    def _lightIsVisible(self, l, p):
        # Every object tests the same origin and normalized direction.
        return self._lightRayIsVisible(Ray(p, l - p))

    def _lightRayIsVisible(self, ray):
        for (o, s) in self.objects:
            t = o.intersectionTime(ray)
            if t is not None and t > EPSILON:
                return False
        return True

    def _visibleLightDirections(self, p):
        for light in self.lightPoints:
            ray = Ray(p, light - p)
            if self._lightRayIsVisible(ray):
                # Shading uses the very same normalized shadow direction.
                yield ray.vector

    def visibleLights(self, p):
        result = []
        for l in self.lightPoints:
            if self._lightIsVisible(l, p):
                result.append(l)
        return result


def addColours(a, scale, b):
    return (a[0] + scale * b[0],
            a[1] + scale * b[1],
            a[2] + scale * b[2])


class SimpleSurface(object):

    def __init__(self, **kwargs):
        self.baseColour = kwargs.get('baseColour', (1, 1, 1))
        self.specularCoefficient = kwargs.get('specularCoefficient', 0.2)
        self.lambertCoefficient = kwargs.get('lambertCoefficient', 0.6)
        self.ambientCoefficient = 1.0 - self.specularCoefficient - self.lambertCoefficient

    def baseColourAt(self, p):
        return self.baseColour

    def colourAt(self, scene, ray, p, normal):
        b = self.baseColourAt(p)

        c = (0, 0, 0)
        if self.specularCoefficient > 0:
            reflectedRay = Ray(p, ray.vector.reflectThrough(normal))
            reflectedColour = scene.rayColour(reflectedRay)
            c = addColours(c, self.specularCoefficient, reflectedColour)

        if self.lambertCoefficient > 0:
            lambertAmount = 0
            for lightDirection in scene._visibleLightDirections(p):
                contribution = lightDirection.dot(normal)
                if contribution > 0:
                    lambertAmount = lambertAmount + contribution
            lambertAmount = min(1, lambertAmount)
            c = addColours(c, self.lambertCoefficient * lambertAmount, b)

        if self.ambientCoefficient > 0:
            c = addColours(c, self.ambientCoefficient, b)

        return c


class CheckerboardSurface(SimpleSurface):

    def __init__(self, **kwargs):
        SimpleSurface.__init__(self, **kwargs)
        self.otherColour = kwargs.get('otherColour', (0, 0, 0))
        self.checkSize = kwargs.get('checkSize', 1)

    def baseColourAt(self, p):
        v = p - Point.ZERO
        # Preserve the original unscaled checker pattern.
        if ((int(abs(v.x) + 0.5)
             + int(abs(v.y) + 0.5)
             + int(abs(v.z) + 0.5)) % 2):
            return self.otherColour
        else:
            return self.baseColour


class BatchedRenderer:
    """The existing sphere/halfspace renderer, with independent rays in columns.

    Coordinate arrays have shape (3, ray_count), with rays in columns.
    Every arithmetic operation is elementwise; no dot-product
    reductions, reassociation, or approximate normalization are used.
    """

    def __init__(self, scene):
        self.scene = scene
        self.geometry = []
        for obj, surface in scene.objects:
            if isinstance(obj, Sphere):
                self.geometry.append((self.coordinates(obj.centre),
                                      obj.radiusSquared, None))
            else:
                self.geometry.append((None, None, self.coordinates(obj.normal)))
        surfaces = [surface for obj, surface in scene.objects]
        self.baseColours = np.array([s.baseColour for s in surfaces],
                                    dtype=np.float64).reshape(-1, 3).T.copy()
        self.otherColours = np.array([
            s.otherColour if isinstance(s, CheckerboardSurface) else s.baseColour
            for s in surfaces], dtype=np.float64).reshape(-1, 3).T.copy()
        self.checker = np.array([isinstance(s, CheckerboardSurface)
                                 for s in surfaces], dtype=bool)
        self.specular = np.array([s.specularCoefficient for s in surfaces])
        self.lambert = np.array([s.lambertCoefficient for s in surfaces])
        self.ambient = np.array([s.ambientCoefficient for s in surfaces])
        self.lights = [self.coordinates(light) for light in scene.lightPoints]

    @staticmethod
    def coordinates(value):
        return np.array([[value.x], [value.y], [value.z]], dtype=np.float64)

    @staticmethod
    def dot(a, b):
        return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])

    @classmethod
    def normalized(cls, vectors):
        factor = 1.0 / np.sqrt(cls.dot(vectors, vectors))
        return factor * vectors

    def intersectionTimes(self, object_index, origins, directions):
        centre, radiusSquared, normal = self.geometry[object_index]
        times = np.full(directions.shape[1], np.nan)
        if centre is not None:
            cp = centre - origins
            v = self.dot(cp, directions)
            discriminant = radiusSquared - (self.dot(cp, cp) - v * v)
            hits = discriminant >= 0
            # Like the scalar branch, only evaluate sqrt for intersecting rays.
            times[hits] = v[hits] - np.sqrt(discriminant[hits])
        else:
            v = self.dot(directions, normal)
            # Preserve the existing halfspace formula and parallel-ray branch.
            np.divide(1, -v, out=times, where=v != 0)
        return times

    def closestHits(self, origins, directions):
        closest = np.full(directions.shape[1], -1, dtype=np.intp)
        times = np.zeros(directions.shape[1])
        for index in range(len(self.geometry)):
            candidate = self.intersectionTimes(index, origins, directions)
            selected = ((candidate > -EPSILON)
                        & ((closest < 0) | (candidate < times)))
            # Object order and strict comparison retain the first hit on ties.
            closest[selected] = index
            times[selected] = candidate[selected]
        return closest, times

    def lightIsVisible(self, origins, directions):
        visible = np.ones(directions.shape[1], dtype=bool)
        remaining = np.arange(directions.shape[1])
        for index in range(len(self.geometry)):
            if remaining.size == 0:
                break
            times = self.intersectionTimes(index, origins[:, remaining],
                                           directions[:, remaining])
            blocked = times > EPSILON
            visible[remaining[blocked]] = False
            remaining = remaining[~blocked]
        return visible

    def normalsAt(self, points, objects):
        normals = np.empty_like(points)
        for index, (centre, radiusSquared, normal) in enumerate(self.geometry):
            selected = objects == index
            if centre is not None:
                normals[:, selected] = self.normalized(points[:, selected] - centre)
            else:
                normals[:, selected] = normal
        return normals

    def baseColoursAt(self, points, objects):
        colours = self.baseColours[:, objects].copy()
        selected = self.checker[objects]
        # int(abs(coordinate) + 0.5), not round-to-even. Take parity before
        # summing so no fixed-width integer conversion limits the checker.
        parity = np.remainder(np.floor(np.abs(points[:, selected]) + 0.5), 2)
        odd = ((parity[0] + parity[1] + parity[2]) % 2) != 0
        alternate = np.flatnonzero(selected)[odd]
        colours[:, alternate] = self.otherColours[:, objects[alternate]]
        return colours

    def rayColours(self, origins, directions, depth=0):
        colours = np.zeros_like(directions)
        if depth > 3:
            return colours
        objects, times = self.closestHits(origins, directions)
        hits = np.flatnonzero(objects >= 0)
        if hits.size == 0:
            return colours
        objects = objects[hits]
        directions = directions[:, hits]
        points = origins[:, hits] + times[hits] * directions
        normals = self.normalsAt(points, objects)
        base = self.baseColoursAt(points, objects)
        shaded = np.zeros_like(points)

        specular = self.specular[objects]
        selected = specular > 0
        if np.any(selected):
            d = directions[:, selected]
            n = normals[:, selected]
            projection = self.dot(d, n)
            reflected = self.normalized(d - 2 * (projection * n))
            reflectedColour = self.rayColours(points[:, selected], reflected, depth + 1)
            shaded[:, selected] = (shaded[:, selected]
                                   + specular[selected] * reflectedColour)

        lambert = self.lambert[objects]
        selected = lambert > 0
        if np.any(selected):
            p = points[:, selected]
            n = normals[:, selected]
            amount = np.zeros(p.shape[1])
            for light in self.lights:
                direction = self.normalized(light - p)
                visible = self.lightIsVisible(p, direction)
                contribution = self.dot(direction[:, visible], n[:, visible])
                positive = contribution > 0
                indices = np.flatnonzero(visible)[positive]
                amount[indices] = amount[indices] + contribution[positive]
            amount = np.minimum(1, amount)
            shaded[:, selected] = (shaded[:, selected]
                                   + (lambert[selected] * amount) * base[:, selected])

        ambient = self.ambient[objects]
        selected = ambient > 0
        shaded[:, selected] = (shaded[:, selected]
                               + ambient[selected] * base[:, selected])
        colours[:, hits] = shaded
        return colours

    def primaryRayBatches(self, width, height, batch_size):
        scene = self.scene
        fovRadians = math.pi * (scene.fieldOfView / 2.0) / 180.0
        halfWidth = math.tan(fovRadians)
        halfHeight = 0.75 * halfWidth
        pixelWidth = (halfWidth * 2) / (width - 1)
        pixelHeight = (halfHeight * 2) / (height - 1)
        eye = Ray(scene.position, scene.lookingAt - scene.position)
        vpRight = eye.vector.cross(Vector.UP).normalized()
        vpUp = vpRight.cross(eye.vector).normalized()
        columns = (self.coordinates(eye.vector)
                   + (np.arange(width) * pixelWidth - halfWidth)
                   * self.coordinates(vpRight))
        rows = ((np.arange(height) * pixelHeight - halfHeight)
                * self.coordinates(vpUp))
        origin = self.coordinates(eye.point)
        for start in range(0, width * height, batch_size):
            pixels = np.arange(start, min(start + batch_size, width * height))
            x = pixels % width
            y = pixels // width
            directions = self.normalized(columns[:, x] + rows[:, y])
            yield x, y, np.broadcast_to(origin, directions.shape), directions

    def render(self, canvas, batch_size):
        for x, y, origins, directions in self.primaryRayBatches(
                canvas.width, canvas.height, batch_size):
            colours = self.rayColours(origins, directions, self.scene.recursionDepth)
            # Keep the existing Python RGB conversion and Canvas interface.
            for px, py, (r, g, b) in zip(x.tolist(), y.tolist(), colours.T.tolist()):
                canvas.plot(px, py, r, g, b)


def bench_raytrace(loops, width, height, filename, batch_size=DEFAULT_BATCH_SIZE):
    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for i in range_it:
        canvas = Canvas(width, height)
        s = Scene()
        s.addLight(Point(30, 30, 10))
        s.addLight(Point(-10, 100, 30))
        s.lookAt(Point(0, 3, 0))
        s.addObject(Sphere(Point(1, 3, -10), 2),
                    SimpleSurface(baseColour=(1, 1, 0)))
        for y in range(6):
            s.addObject(Sphere(Point(-3 - y * 0.4, 2.3, -5), 0.4),
                        SimpleSurface(baseColour=(y / 6.0, 1 - y / 6.0, 0.5)))
        s.addObject(Halfspace(Point(0, 0, 0), Vector.UP),
                    CheckerboardSurface())
        s.render(canvas, batch_size)

    dt = pyperf.perf_counter() - t0

    if filename:
        canvas.write_ppm(filename)
    return dt


def add_cmdline_args(cmd, args):
    cmd.append("--width=%s" % args.width)
    cmd.append("--height=%s" % args.height)
    cmd.append("--batch-size=%s" % args.batch_size)
    if args.filename:
        cmd.extend(("--filename", args.filename))


if __name__ == "__main__":
    runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
    cmd = runner.argparser
    cmd.add_argument("--width",
                     type=int, default=DEFAULT_WIDTH,
                     help="Image width (default: %s)" % DEFAULT_WIDTH)
    cmd.add_argument("--height",
                     type=int, default=DEFAULT_HEIGHT,
                     help="Image height (default: %s)" % DEFAULT_HEIGHT)
    cmd.add_argument("--filename", metavar="FILENAME.PPM",
                     help="Output filename of the PPM picture")
    cmd.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                     help="Rays per NumPy batch (default: %s)" % DEFAULT_BATCH_SIZE)

    args = runner.parse_args()
    runner.metadata['description'] = "Simple raytracer"
    runner.metadata['raytrace_width'] = args.width
    runner.metadata['raytrace_height'] = args.height
    runner.metadata['raytrace_batch_size'] = args.batch_size
    runner.metadata['raytrace_backend'] = 'numpy'
    runner.metadata['numpy_version'] = np.__version__
    runner.metadata['numpy_thread_limit'] = 1

    runner.bench_time_func('raytrace', bench_raytrace,
                           args.width, args.height,
                           args.filename, args.batch_size)
