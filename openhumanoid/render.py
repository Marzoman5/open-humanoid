"""Render review images of a variant's sim model (primitive or CAD-derived): front, side, 3/4, plus a contact sheet.
Used at human review gates so the maintainer can see the robot without opening a viewer."""
from __future__ import annotations

from pathlib import Path

from .spec import expand_joints, generated_dir

VIEWS = {"front": (180, -5), "side": (90, -5), "three_quarter": (140, -15), "back": (0, -5)}


def render(spec: dict, width: int = 640, height: int = 800, views: list[str] | None = None) -> list[Path]:
    import mujoco
    from PIL import Image

    from . import simgen

    sim_dir = generated_dir(spec) / "sim"
    cad_model = Path(spec["_dir"]) / "cad" / "export" / "robot.xml"
    path = cad_model if cad_model.exists() else sim_dir / f"{spec['id']}.xml"
    if not path.exists():
        path = simgen.write_mjcf(spec)
    model = mujoco.MjModel.from_xml_path(str(path))
    model.vis.global_.offwidth = max(model.vis.global_.offwidth, width)
    model.vis.global_.offheight = max(model.vis.global_.offheight, height)
    data = mujoco.MjData(model)
    sizing = simgen.load_sizing(spec)
    joints = [j for j in expand_joints(spec, sizing["joints_base"]) if simgen.JOINT_BODY.get(j["base"])]
    for name, q in simgen.stand_pose(spec, joints).items():
        data.joint(name).qpos[0] = q
    mujoco.mj_forward(model, data)

    h = sizing["height_m"]
    cam = mujoco.MjvCamera()
    cam.lookat[:] = [0, 0, h * 0.5]
    cam.distance = h * 2.4
    out_dir = generated_dir(spec) / "renders"
    out_dir.mkdir(exist_ok=True)
    renderer = mujoco.Renderer(model, height, width)
    files, images = [], []
    for name in views or list(VIEWS):
        cam.azimuth, cam.elevation = VIEWS[name]
        renderer.update_scene(data, camera=cam)
        img = Image.fromarray(renderer.render())
        f = out_dir / f"{name}.png"
        img.save(f)
        files.append(f)
        images.append(img)
    sheet = Image.new("RGB", (width * len(images), height), "white")
    for i, img in enumerate(images):
        sheet.paste(img, (i * width, 0))
    f = out_dir / "sheet.png"
    sheet.save(f)
    files.append(f)
    renderer.close()
    return files
