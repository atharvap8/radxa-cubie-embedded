#!/usr/bin/env python3
"""
ISM6HG256X IMU Visualizer - I2C Direct
=======================================
Reads orientation from ISM6HG256X over I2C-7 on Radxa Cubie A7A.
Renders a 3D cube tracking the physical orientation of the sensor.

Requires: pygame, PyOpenGL, smbus2
"""

import sys
import time
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

from ism6hg256x import ISM6HG256X, I2C_ADDR_SA0_LOW

# ==================== CONFIGURATION ====================
I2C_BUS     = 7
I2C_ADDRESS = I2C_ADDR_SA0_LOW
WINDOW_SIZE = (1280, 800)
TARGET_FPS  = 60

# ==================== CUBE GEOMETRY ====================
cube_vertices = (
    ( 1, -1, -1), ( 1,  1, -1), (-1,  1, -1), (-1, -1, -1),
    ( 1, -1,  1), ( 1,  1,  1), (-1, -1,  1), (-1,  1,  1)
)
cube_edges = (
    (0,1), (0,3), (0,4), (2,1), (2,3), (2,7),
    (6,3), (6,4), (6,7), (5,1), (5,4), (5,7)
)
cube_faces = (
    (0,1,2,3), (3,2,7,6), (6,7,5,4),
    (4,5,1,0), (1,5,7,2), (4,0,3,6)
)
face_colors = (
    (0.9, 0.2, 0.2), (0.2, 0.9, 0.2), (0.2, 0.2, 0.9),
    (0.9, 0.9, 0.2), (0.9, 0.2, 0.9), (0.2, 0.9, 0.9)
)

# ==================== RENDERING ====================

def draw_blender_background():
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(-1, 1, -1, 1, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glBegin(GL_QUADS)
    glColor3f(0.25, 0.25, 0.27)
    glVertex2f(-1, 1); glVertex2f(1, 1)
    glColor3f(0.40, 0.40, 0.42)
    glVertex2f(1, -1); glVertex2f(-1, -1)
    glEnd()
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)


def draw_origin_grid():
    grid_size = 20
    grid_divisions = 40
    grid_step = grid_size * 2.0 / grid_divisions
    glLineWidth(1)
    glBegin(GL_LINES)
    for i in range(grid_divisions + 1):
        pos = -grid_size + i * grid_step
        distance_factor = abs(pos) / grid_size
        b = 0.35 - distance_factor * 0.15
        glColor3f(b, b, b)
        glVertex3f(-grid_size, 0, pos); glVertex3f(grid_size, 0, pos)
        glVertex3f(pos, 0, -grid_size); glVertex3f(pos, 0, grid_size)
    glEnd()
    glLineWidth(2)
    glBegin(GL_LINES)
    glColor3f(0.7, 0.2, 0.2)
    glVertex3f(-grid_size, 0, 0); glVertex3f(grid_size, 0, 0)
    glColor3f(0.2, 0.2, 0.7)
    glVertex3f(0, 0, -grid_size); glVertex3f(0, 0, grid_size)
    glEnd()
    glLineWidth(2)
    glBegin(GL_LINES)
    glColor3f(0.2, 0.7, 0.2)
    glVertex3f(0, -grid_size/2, 0); glVertex3f(0, grid_size/2, 0)
    glEnd()
    glPushMatrix()
    glColor3f(0.9, 0.9, 0.9)
    quadric = gluNewQuadric()
    gluSphere(quadric, 0.15, 16, 16)
    glPopMatrix()


def draw_cube():
    glBegin(GL_QUADS)
    for i, face in enumerate(cube_faces):
        glColor3fv(face_colors[i])
        for vi in face:
            glVertex3fv(cube_vertices[vi])
    glEnd()
    glColor3f(0, 0, 0)
    glLineWidth(2.5)
    glBegin(GL_LINES)
    for edge in cube_edges:
        for vi in edge:
            glVertex3fv(cube_vertices[vi])
    glEnd()


# ==================== MAIN ====================

def main():
    print(f"Opening ISM6HG256X on /dev/i2c-{I2C_BUS} at 0x{I2C_ADDRESS:02X} ...")
    try:
        imu = ISM6HG256X(bus_number=I2C_BUS, address=I2C_ADDRESS)
        print("  Device identified.  Sensor active.\n")
    except Exception as e:
        print(f"  Failed: {e}")
        sys.exit(1)

    pygame.init()
    pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    pygame.display.set_caption('ISM6HG256X - I2C Visualizer')

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_LINE_SMOOTH)
    glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
    gluPerspective(45, (WINDOW_SIZE[0] / WINDOW_SIZE[1]), 0.1, 100.0)
    glTranslatef(0, -3, -25)

    clock = pygame.time.Clock()
    roll = pitch = yaw = 0.0
    camera_rot_x, camera_rot_y = 25, -20

    print("Controls: Arrow Keys (rotate view) | ESC (quit)")
    print("\nOrientation:")
    running = True

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            keys = pygame.key.get_pressed()
            if keys[K_LEFT]:  camera_rot_y -= 2
            if keys[K_RIGHT]: camera_rot_y += 2
            if keys[K_UP]:    camera_rot_x -= 2
            if keys[K_DOWN]:  camera_rot_x += 2

            r, p, y = imu.update_orientation()
            if r is not None:
                roll, pitch, yaw = r, p, -y
                print(f"\rRoll: {roll:7.2f}  Pitch: {pitch:7.2f}  Yaw: {yaw:7.2f}", end='', flush=True)

            draw_blender_background()
            glClear(GL_DEPTH_BUFFER_BIT)
            glPushMatrix()
            glRotatef(camera_rot_x, 1, 0, 0)
            glRotatef(camera_rot_y, 0, 1, 0)
            draw_origin_grid()
            glTranslatef(0, 5, 0)
            glRotatef(roll,  1, 0, 0)
            glRotatef(pitch, 0, 1, 0)
            glRotatef(yaw,   0, 0, 1)
            draw_cube()
            glPopMatrix()
            pygame.display.flip()
            clock.tick(TARGET_FPS)
    except KeyboardInterrupt:
        pass

    print("\n\nShutting down ...")
    imu.close()
    pygame.quit()


if __name__ == "__main__":
    main()
