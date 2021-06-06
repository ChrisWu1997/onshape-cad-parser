import pprint
import os
import copy
import numpy as np
from collections import OrderedDict
from utils import xyz_list2dict, angle_from_vector_to_x

# OnShape naming to Fusion360 naming format
EXTENT_TYPE_MAP = {'BLIND': 'OneSideFeatureExtentType', 'SYMMETRIC': 'SymmetricFeatureExtentType'}
OPERATION_MAP = {'NEW': 'NewBodyFeatureOperation', 'ADD': 'JoinFeatureOperation',
                 'REMOVE': 'CutFeatureOperation', 'INTERSECT': 'IntersectFeatureOperation'}


class FeatureListParser(object):
    """A parser for OnShape feature list (construction sequence)"""
    def __init__(self, client, did, wid, eid, data_id=None):
        self.c = client

        self.did = did
        self.wid = wid
        self.eid = eid
        self.data_id = data_id

        self.feature_list = self.c.get_features(did, wid, eid).json()

        self.profile2sketch = {}

    @staticmethod
    def parse_feature_param(feat_param_data):
        param_dict = {}
        for i, param_item in enumerate(feat_param_data):
            param_msg = param_item['message']
            param_id = param_msg['parameterId']
            if 'queries' in param_msg:
                param_value = []
                for i in range(len(param_msg['queries'])):
                    param_value.extend(param_msg['queries'][i]['message']['geometryIds']) # FIXME: could be error-prone
            elif 'expression' in param_msg:
                param_value = param_msg['expression']
            elif 'value' in param_msg:
                param_value = param_msg['value']
            else:
                raise NotImplementedError('param_msg:\n{}'.format(param_msg))

            param_dict.update({param_id: param_value})
        return param_dict

    def _parse_sketch(self, feature_data):
        sket_parser = SketchParser(self.c, feature_data, self.did, self.wid, self.eid)
        save_dict = sket_parser.parse_to_fusion360_format()
        return save_dict

    def _expr2meter(self, expr):
        return self.c.expr2meter(self.did, self.wid, self.eid, expr)

    def _locateSketchProfile(self, geo_ids):
        return [{"profile": k, "sketch": self.profile2sketch[k]} for k in geo_ids]

    def _parse_extrude(self, feature_data):
        param_dict = self.parse_feature_param(feature_data['parameters'])
        if 'hasOffset' in param_dict and param_dict['hasOffset'] is True:
            raise NotImplementedError("extrude with offset not supported: {}".format(param_dict['hasOffset']))

        entities = param_dict['entities'] # geometryIds for target face
        profiles = self._locateSketchProfile(entities)

        extent_one = self._expr2meter(param_dict['depth'])
        if param_dict['endBound'] == 'SYMMETRIC':
            extent_one = extent_one / 2
        if 'oppositeDirection' in param_dict and param_dict['oppositeDirection'] is True:
            extent_one = -extent_one
        extent_two = 0.0
        if param_dict['endBound'] not in ['BLIND', 'SYMMETRIC']:
            raise NotImplementedError("endBound type not supported: {}".format(param_dict['endBound']))
        elif 'hasSecondDirection' in param_dict and param_dict['hasSecondDirection'] is True:
            if param_dict['secondDirectionBound'] != 'BLIND':
                raise NotImplementedError("secondDirectionBound type not supported: {}".format(param_dict['endBound']))
            extent_type = 'TwoSidesFeatureExtentType'
            extent_two = self._expr2meter(param_dict['secondDirectionDepth'])
            if 'secondDirectionOppositeDirection' in param_dict \
                and str(param_dict['secondDirectionOppositeDirection']) == 'true':
                extent_two = -extent_two
        else:
            extent_type = EXTENT_TYPE_MAP[param_dict['endBound']]

        operation = OPERATION_MAP[param_dict['operationType']]

        save_dict = {"name": feature_data['name'],
                    "type": "ExtrudeFeature",
                    "profiles": profiles,
                    "operation": operation,
                    "start_extent": {"type": "ProfilePlaneStartDefinition"},
                    "extent_type": extent_type,
                    "extent_one": {
                        "distance": {
                            "type": "ModelParameter",
                            "value": extent_one,
                            "name": "none",
                            "role": "AlongDistance"
                        },
                        "taper_angle": {
                            "type": "ModelParameter",
                            "value": 0.0,
                            "name": "none",
                            "role": "TaperAngle"
                        },
                        "type": "DistanceExtentDefinition"
                    },
                    "extent_two": {
                        "distance": {
                            "type": "ModelParameter",
                            "value": extent_two,
                            "name": "none",
                            "role": "AgainstDistance"
                        },
                        "taper_angle": {
                            "type": "ModelParameter",
                            "value": 0.0,
                            "name": "none",
                            "role": "Side2TaperAngle"
                        },
                        "type": "DistanceExtentDefinition"
                    },
                    }
        return save_dict

    def _parse_boundingBox(self):
        bbox_info = self.c.eval_boundingBox(self.did, self.wid, self.eid)
        result = {"type": "BoundingBox3D",
                  "max_point": xyz_list2dict(bbox_info['maxCorner']),
                  "min_point": xyz_list2dict(bbox_info['minCorner'])}
        return result

    def parse(self):
        """parse into fusion360 gallery format, 
        only sketch and extrusion are supported.
        """
        result = {"entities": OrderedDict(), "properties": {}, "sequence": []}
        try:
            bbox = self._parse_boundingBox()
        except Exception as e:
            print(self.data_id, "bounding box failed:", e)
            return result
        result["properties"].update({"bounding_box": bbox})

        for i, feat_item in enumerate(self.feature_list['features']):
            feat_data = feat_item['message']
            feat_type = feat_data['featureType']
            feat_Id = feat_data['featureId']

            try:
                if feat_type == 'newSketch':
                    feat_dict = self._parse_sketch(feat_data)
                    for k in feat_dict['profiles'].keys():
                        self.profile2sketch.update({k: feat_Id})
                elif feat_type == 'extrude':
                    feat_dict = self._parse_extrude(feat_data)
                else:
                    raise NotImplementedError(self.data_id, "unsupported feature type: {}".format(feat_type))
            except Exception as e:
                print(self.data_id, "parse feature failed:", e)
                break
            result["entities"].update({feat_Id: feat_dict})
            result["sequence"].append({"index": i, "type": feat_dict['type'], "entity": feat_Id})
        return result


class SketchParser(object):
    """A parser for OnShape sketch feature list"""
    def __init__(self, client, feat_data, did, wid, eid, data_id=None):
        self.c = client
        self.feat_id = feat_data['featureId']
        self.feat_name = feat_data['name']
        self.feat_param = FeatureListParser.parse_feature_param(feat_data['parameters'])

        self.did = did
        self.wid = wid
        self.eid = eid
        self.data_id = data_id

        geo_id = self.feat_param["sketchPlane"][0]
        response = self.c.get_entity_by_id(did, wid, eid, [geo_id], "FACE")
        self.plane = self.c.parse_face_msg(response.json()['result']['message']['value'])[0]

        self.geo_topo = self.c.eval_sketch_topology_by_adjacency(did, wid, eid, self.feat_id)
        self._to_local_coordinates()
        self._build_lookup()

    def _to_local_coordinates(self):
        """transform into local coordinate system"""
        self.origin = np.array(self.plane["origin"])
        self.z_axis = np.array(self.plane["normal"])
        self.x_axis = np.array(self.plane["x"])
        self.y_axis = np.cross(self.plane["normal"], self.plane["x"])
        for item in self.geo_topo["vertices"]:
            old_vec = np.array(item["param"]["Vector"])
            new_vec = old_vec - self.origin
            item["param"]["Vector"] = [np.dot(new_vec, self.x_axis), 
                                       np.dot(new_vec, self.y_axis), 
                                       np.dot(new_vec, self.z_axis)]

        for item in self.geo_topo["edges"]:
            if item["param"]["type"] == "Circle":
                old_vec = np.array(item["param"]["coordSystem"]["origin"])
                new_vec = old_vec - self.origin
                item["param"]["coordSystem"]["origin"] = [np.dot(new_vec, self.x_axis),
                                                          np.dot(new_vec, self.y_axis),
                                                          np.dot(new_vec, self.z_axis)]

    def _build_lookup(self):
        """build a look up table with entity ID as key"""
        edge_table = {}
        for item in self.geo_topo["edges"]:
            edge_table.update({item["id"]: item})
        self.edge_table = edge_table

        vert_table = {}
        for item in self.geo_topo["vertices"]:
            vert_table.update({item["id"]: item})
        self.vert_table = vert_table

    def _parse_edges_to_loops(self, all_edge_ids):
        """sort all edges of a face into loops."""
        # FIXME: this can be error-prone. bug situation: one vertex connected to 3 edges
        vert2edge = {}
        for edge_id in all_edge_ids:
            item = self.edge_table[edge_id]
            for vert in item["vertices"]:
                if vert not in vert2edge.keys():
                    vert2edge.update({vert: [item["id"]]})
                else:
                    vert2edge[vert].append(item["id"])

        all_loops = []
        unvisited_edges = copy.copy(all_edge_ids)
        while len(unvisited_edges) > 0:
            cur_edge = unvisited_edges[0]
            unvisited_edges.remove(cur_edge)
            loop_edge_ids = [cur_edge]
            if len(self.edge_table[cur_edge]["vertices"]) == 0:  # no corresponding vertices
                pass
            else:
                loop_start_point, cur_end_point = self.edge_table[cur_edge]["vertices"][0], \
                                                  self.edge_table[cur_edge]["vertices"][-1]
                while cur_end_point != loop_start_point:
                    # find next connected edge
                    edges = vert2edge[cur_end_point][:]
                    edges.remove(cur_edge)
                    cur_edge = edges[0]
                    loop_edge_ids.append(cur_edge)
                    unvisited_edges.remove(cur_edge)

                    # find next enc_point
                    points = self.edge_table[cur_edge]["vertices"][:]
                    points.remove(cur_end_point)
                    cur_end_point = points[0]
            all_loops.append(loop_edge_ids)
        return all_loops

    def _parse_edge_to_fusion360_format(self, edge_id):
        """parse a edge into fusion360 gallery format. Only support 'Line', 'Circle' and 'Arc'."""
        edge_data = self.edge_table[edge_id]
        edge_type = edge_data["param"]["type"]
        if edge_type == "Line":
            start_id, end_id = edge_data["vertices"]
            start_point = xyz_list2dict(self.vert_table[start_id]["param"]["Vector"])
            end_point = xyz_list2dict(self.vert_table[end_id]["param"]["Vector"])
            curve_dict = OrderedDict({"type": "Line3D", "start_point": start_point,
                                      "end_point": end_point, "curve": edge_id})
        elif edge_type == "Circle" and len(edge_data["vertices"]) == 2: # an Arc
            radius = edge_data["param"]["radius"]
            start_id, end_id = edge_data["vertices"]
            start_point = xyz_list2dict(self.vert_table[start_id]["param"]["Vector"])
            end_point = xyz_list2dict(self.vert_table[end_id]["param"]["Vector"])
            center_point = xyz_list2dict(edge_data["param"]["coordSystem"]["origin"])
            normal = xyz_list2dict(edge_data["param"]["coordSystem"]["zAxis"])

            start_vec = np.array(self.vert_table[start_id]["param"]["Vector"]) - \
                        np.array(edge_data["param"]["coordSystem"]["origin"])
            end_vec = np.array(self.vert_table[end_id]["param"]["Vector"]) - \
                      np.array(edge_data["param"]["coordSystem"]["origin"])
            start_vec = start_vec / np.linalg.norm(start_vec)
            end_vec = end_vec / np.linalg.norm(end_vec)

            start_angle = angle_from_vector_to_x(start_vec)
            end_angle = angle_from_vector_to_x(end_vec)
            # keep it counter-clockwise first
            if start_angle > end_angle:
                start_angle, end_angle = end_angle, start_angle
                start_vec, end_vec = end_vec, start_vec
            sweep_angle = abs(start_angle - end_angle)

            # # decide direction arc by curve length
            # edge_len = self.c.eval_curveLength(self.did, self.wid, self.eid, edge_id)
            # _len = sweep_angle * radius
            # _len_other = (2 * np.pi - sweep_angle) * radius
            # if abs(edge_len - _len) > abs(edge_len - _len_other):
            #     sweep_angle = 2 * np.pi - sweep_angle
            #     start_vec = end_vec

            # decide direction by middle point
            midpoint = self.c.eval_curve_midpoint(self.did, self.wid, self.eid, edge_id)
            mid_vec = np.array(midpoint) - self.origin
            mid_vec = np.array([np.dot(mid_vec, self.x_axis), np.dot(mid_vec, self.y_axis), np.dot(mid_vec, self.z_axis)])
            mid_vec = mid_vec - np.array(edge_data["param"]["coordSystem"]["origin"])
            mid_vec = mid_vec / np.linalg.norm(mid_vec)
            mid_angle_real = angle_from_vector_to_x(mid_vec)
            mid_angle_now = (start_angle + end_angle) / 2            
            if round(mid_angle_real, 3) != round(mid_angle_now, 3):
                sweep_angle = 2 * np.pi - sweep_angle
                start_vec = end_vec

            ref_vec_dict = xyz_list2dict(list(start_vec))
            curve_dict = OrderedDict({"type": "Arc3D", "start_point": start_point, "end_point": end_point,
                          "center_point": center_point, "radius": radius, "normal": normal,
                          "start_angle": 0.0, "end_angle": sweep_angle, "reference_vector": ref_vec_dict,
                          "curve": edge_id})
        elif edge_type == "Circle" and len(edge_data["vertices"]) < 2:
            # NOTE: treat the circle with only one connected vertex as a full circle
            radius = edge_data["param"]["radius"]
            center_point = xyz_list2dict(edge_data["param"]["coordSystem"]["origin"])
            normal = xyz_list2dict(edge_data["param"]["coordSystem"]["zAxis"])
            curve_dict = OrderedDict({"type": "Circle3D", "center_point": center_point, "radius": radius, "normal": normal,
                          "curve": edge_id})
        else:
            raise NotImplementedError(edge_type, edge_data["vertices"])
        return curve_dict

    def parse_to_fusion360_format(self):
        """parse sketch feature into fusion360 gallery format"""
        name = self.feat_name

        # transform & reference plane
        transform_dict = {"origin": xyz_list2dict(self.plane["origin"]),
                          "z_axis": xyz_list2dict(self.plane["normal"]),
                          "x_axis": xyz_list2dict(self.plane["x"]),
                          "y_axis": xyz_list2dict(list(np.cross(self.plane["normal"], self.plane["x"])))}
        ref_plane_dict = {}

        # profiles
        profiles_dict = {}
        for item in self.geo_topo['faces']:
            # profile level
            profile_id = item['id']
            all_edge_ids = item['edges']
            edge_ids_per_loop = self._parse_edges_to_loops(all_edge_ids)
            all_loops = []
            for loop in edge_ids_per_loop:
                curves = [self._parse_edge_to_fusion360_format(edge_id) for edge_id in loop]
                loop_dict = {"is_outer": True, "profile_curves": curves}
                all_loops.append(loop_dict)
            profiles_dict.update({profile_id: {"loops": all_loops, "properties": {}}})

        entity_dict = {"name": name, "type": "Sketch", "profiles": profiles_dict,
                       "transform": transform_dict, "reference_plane": ref_plane_dict}
        return entity_dict
