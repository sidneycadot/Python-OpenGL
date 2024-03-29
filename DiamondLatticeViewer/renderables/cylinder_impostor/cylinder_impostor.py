"""This module implements the RenderableCylinderImpostor class."""

import os

from PIL import Image

import numpy as np

from utilities.opengl_symbols import *
from utilities.matrices import apply_transform_to_vertices, scale
from utilities.opengl_utilities import create_opengl_program, define_vertex_attributes, gl_get_uniform_location_checked
from utilities.geometry import make_unit_cylinder_triangles

from renderables.renderable import Renderable
from utilities.world import World


def make_cylinder_impostor_triangle_vertex_data(transformation_matrix):

    if transformation_matrix is None:
        transformation_matrix = np.identity(4)

    triangles = make_unit_cylinder_triangles(subdivision_count=6, capped=True)

    triangle_vertices = np.array(triangles).reshape(-1, 3)

    impostor_scale_matrix = scale((1.2, 1.2, 1.01))

    triangle_vertices = apply_transform_to_vertices(transformation_matrix @ impostor_scale_matrix, triangle_vertices)

    vbo_dtype = np.dtype([
        ("a_vertex", np.float32, 3)
    ])

    vbo_data = np.empty(dtype=vbo_dtype, shape=len(triangle_vertices))

    vbo_data["a_vertex"] = triangle_vertices  # Oversize the impostor.

    return vbo_data


class RenderableCylinderImpostor(Renderable):

    def __init__(self, world: World, m_xform=None):

        self._world = world

        # Compile the shader program.

        shader_source_path = os.path.join(os.path.dirname(__file__), "cylinder_impostor")
        (self._shaders, self._shader_program) = create_opengl_program(shader_source_path)

        # Find the location of uniform shader program variables.

        self._projection_matrix_location = gl_get_uniform_location_checked(self._shader_program, "projection_matrix")

        self._view_model_matrix_location = gl_get_uniform_location_checked(self._shader_program, "view_model_matrix")
        self._projection_view_model_matrix_location = gl_get_uniform_location_checked(self._shader_program, "projection_view_model_matrix")
        self._transposed_inverse_view_matrix_location = gl_get_uniform_location_checked(self._shader_program, "transposed_inverse_view_matrix")
        self._transposed_inverse_view_model_matrix_location = gl_get_uniform_location_checked(self._shader_program, "transposed_inverse_view_model_matrix")

        self._impostor_mode_location = gl_get_uniform_location_checked(self._shader_program, "impostor_mode")

        self._texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # Make vertex buffer data.

        vbo_data = make_cylinder_impostor_triangle_vertex_data(m_xform)

        print("Cylinder impostor size: {} triangles, {} vertices, {} bytes ({} bytes per triangle).".format(
            vbo_data.size // 3, vbo_data.size, vbo_data.nbytes, vbo_data.itemsize))

        self._vertex_count = vbo_data.size

        # Make texture.

        texture_image_path = os.path.join(os.path.dirname(__file__), "earth.png")

        with Image.open(texture_image_path) as im:
            image = np.array(im)

        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.shape[1], image.shape[0], 0, GL_RGB, GL_UNSIGNED_BYTE, image)
        glGenerateMipmap(GL_TEXTURE_2D)

        # Make Vertex Buffer Object (VBO)
        self._vbo = glGenBuffers(1)

        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, vbo_data.nbytes, vbo_data, GL_STATIC_DRAW)

        # Create a vertex array object (VAO)
        # If a GL_ARRAY_BUFFER is bound, it will be associated with the VAO.

        self._vao = glGenVertexArrays(1)
        glBindVertexArray(self._vao)

        # Define attributes based on the vbo_data element type and enable them.
        define_vertex_attributes(vbo_data.dtype, True)

        # Unbind VAO
        glBindVertexArray(0)

        # Unbind VBO.
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def close(self):

        if self._vao is not None:
            glDeleteVertexArrays(1, (self._vao, ))
            self._vao = None

        if self._vbo is not None:
            glDeleteBuffers(1, (self._vbo, ))
            self._vbo = None

        if self._shader_program is not None:
            glDeleteProgram(self._shader_program)
            self._shader_program = None

        if self._shaders is not None:
            for shader in self._shaders:
                glDeleteShader(shader)
            self._shaders = None

    def render(self, projection_matrix, view_matrix, model_matrix):

        world = self._world

        glUseProgram(self._shader_program)

        glUniformMatrix4fv(self._projection_matrix_location, 1, GL_TRUE, projection_matrix.astype(np.float32))
        glUniformMatrix4fv(self._view_model_matrix_location, 1, GL_TRUE, (view_matrix @ model_matrix).astype(np.float32))
        glUniformMatrix4fv(self._projection_view_model_matrix_location, 1, GL_TRUE, (projection_matrix @ view_matrix @ model_matrix).astype(np.float32))
        glUniformMatrix4fv(self._transposed_inverse_view_matrix_location, 1, GL_TRUE, np.linalg.inv(view_matrix).T.astype(np.float32))
        glUniformMatrix4fv(self._transposed_inverse_view_model_matrix_location, 1, GL_TRUE, np.linalg.inv(view_matrix @ model_matrix).T.astype(np.float32))

        glUniform1ui(self._impostor_mode_location, world.get_variable("impostor_mode"))

        glBindTexture(GL_TEXTURE_2D, self._texture)
        glBindVertexArray(self._vao)
        glEnable(GL_CULL_FACE)
        glDrawArrays(GL_TRIANGLES, 0, self._vertex_count)
