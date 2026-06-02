#target photoshop
app.displayDialogs = DialogModes.NO;

var DOC_W = 1080;
var DOC_H = 1920;
var PREVIEW_PATH = "D:/CrealityOS/workspace/psd-handoff/no-timer-demo/no_timer_game_psd_preview_v3_source_assets.png";
var GREEN_BALL_PATH = "D:/CrealityOS/workspace/psd-handoff/no-timer-demo/source_assets/Ball_9.png";
var PURPLE_BALL_PATH = "D:/CrealityOS/workspace/psd-handoff/no-timer-demo/source_assets/Ball_3.png";
var BALL_SHADOW_PATH = "D:/CrealityOS/workspace/psd-handoff/no-timer-demo/source_assets/marbleShadow.png";

function rgb(r, g, b) {
  var c = new SolidColor();
  c.rgb.red = r;
  c.rgb.green = g;
  c.rgb.blue = b;
  return c;
}

function makeGroup(name, parent) {
  var g = parent.layerSets.add();
  g.name = name;
  return g;
}

function fillRect(doc, parent, name, x, y, w, h, color) {
  var layer = doc.artLayers.add();
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  doc.selection.select([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]);
  doc.selection.fill(color, ColorBlendMode.NORMAL, 100, false);
  doc.selection.deselect();
  return layer;
}

function fillCircleApprox(doc, parent, name, cx, cy, r, color) {
  var pts = [];
  for (var i = 0; i < 48; i++) {
    var a = Math.PI * 2 * i / 48;
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  var layer = doc.artLayers.add();
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  doc.selection.select(pts);
  doc.selection.fill(color, ColorBlendMode.NORMAL, 100, false);
  doc.selection.deselect();
  return layer;
}

function boundsPx(layer) {
  var b = layer.bounds;
  return [b[0].as("px"), b[1].as("px"), b[2].as("px"), b[3].as("px")];
}

function centerLayer(layer, cx, cy) {
  var b = boundsPx(layer);
  var currentCx = (b[0] + b[2]) / 2;
  var currentCy = (b[1] + b[3]) / 2;
  layer.translate(cx - currentCx, cy - currentCy);
}

function placePngLayer(doc, parent, path, name, cx, cy, targetW, targetH, opacity) {
  var f = new File(path);
  if (!f.exists) return null;
  var src = app.open(f);
  src.activeLayer.name = name;
  src.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
  src.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument = doc;
  var layer = doc.activeLayer;
  layer.name = name;
  layer.move(parent, ElementPlacement.INSIDE);
  var b = boundsPx(layer);
  var w = b[2] - b[0];
  var h = b[3] - b[1];
  if (w > 0 && h > 0) layer.resize(targetW / w * 100, targetH / h * 100, AnchorPosition.MIDDLECENTER);
  centerLayer(layer, cx, cy);
  if (opacity != undefined) layer.opacity = opacity;
  return layer;
}

function addEditableText(doc, parent) {
  var layer = doc.artLayers.add();
  layer.name = "title_text_EDITABLE_NO_TIMER";
  layer.kind = LayerKind.TEXT;
  layer.move(parent, ElementPlacement.INSIDE);
  var t = layer.textItem;
  t.contents = "NO TIMER!";
  t.size = 127;
  t.font = "Arial-BoldMT";
  t.color = rgb(255, 255, 255);
  t.justification = Justification.CENTER;
  t.position = [DOC_W / 2, 278];
  return layer;
}

function placeReference(doc, parent) {
  try {
    var f = new File(PREVIEW_PATH);
    if (!f.exists) return;
    var refDoc = app.open(f);
    refDoc.activeLayer.name = "reference_preview_locked";
    refDoc.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
    refDoc.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    doc.activeLayer.name = "reference_preview_locked";
    doc.activeLayer.opacity = 35;
    doc.activeLayer.move(parent, ElementPlacement.INSIDE);
    doc.activeLayer.allLocked = true;
  } catch (e) {}
}

var doc = app.documents.add(DOC_W, DOC_H, 72, "no_timer_game_production_handoff", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);

var bg = makeGroup("01_BACKGROUND", doc);
var board = makeGroup("02_BOARD_CONTAINER", doc);
var objects = makeGroup("03_GAME_OBJECTS", doc);
var greenBalls = makeGroup("03A_GREEN_BALLS", objects);
var purpleBalls = makeGroup("03B_PURPLE_BALLS", objects);
var counters = makeGroup("04_INTERACTION_COUNTERS", doc);
var title = makeGroup("05_TOP_UI_TITLE", doc);
var guides = makeGroup("99_REFERENCE_AND_GUIDES", doc);

fillRect(doc, bg, "background_dark_blue_FILL", 0, 0, DOC_W, DOC_H, rgb(44, 60, 74));

fillRect(doc, board, "board_outer_frame_placeholder", 41, 453, 1003, 1136, rgb(130, 149, 196));
fillRect(doc, board, "board_tile_grid_base_placeholder", 68, 482, 953, 1089, rgb(166, 185, 204));
fillRect(doc, board, "maze_dark_cutout_placeholder", 178, 612, 147, 406, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_2", 598, 748, 154, 137, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_3", 53, 1169, 284, 91, rgb(45, 60, 74));
fillRect(doc, board, "maze_dark_cutout_placeholder_4", 612, 1157, 140, 260, rgb(45, 60, 74));

var balls = [
  {name: 'ball_01_purple_139_544', x: 139, y: 544, color: 'purple'},
  {name: 'ball_02_green_272_544', x: 272, y: 544, color: 'green'},
  {name: 'ball_03_purple_411_544', x: 411, y: 544, color: 'purple'},
  {name: 'ball_04_green_536_544', x: 536, y: 544, color: 'green'},
  {name: 'ball_05_green_817_544', x: 817, y: 544, color: 'green'},
  {name: 'ball_06_green_411_683', x: 411, y: 683, color: 'green'},
  {name: 'ball_07_green_684_683', x: 684, y: 683, color: 'green'},
  {name: 'ball_08_purple_139_822', x: 139, y: 822, color: 'purple'},
  {name: 'ball_09_purple_817_822', x: 817, y: 822, color: 'purple'},
  {name: 'ball_10_green_956_822', x: 956, y: 822, color: 'green'},
  {name: 'ball_11_purple_139_953', x: 139, y: 953, color: 'purple'},
  {name: 'ball_12_green_411_953', x: 411, y: 953, color: 'green'},
  {name: 'ball_13_purple_544_953', x: 544, y: 953, color: 'purple'},
  {name: 'ball_14_green_684_953', x: 684, y: 953, color: 'green'},
  {name: 'ball_15_green_139_1083', x: 139, y: 1083, color: 'green'},
  {name: 'ball_16_purple_956_1083', x: 956, y: 1083, color: 'purple'},
  {name: 'ball_17_purple_411_1222', x: 411, y: 1222, color: 'purple'},
  {name: 'ball_18_green_544_1222', x: 544, y: 1222, color: 'green'},
  {name: 'ball_19_green_956_1222', x: 956, y: 1222, color: 'green'},
  {name: 'ball_20_green_139_1358', x: 139, y: 1358, color: 'green'},
  {name: 'ball_21_purple_956_1358', x: 956, y: 1358, color: 'purple'},
  {name: 'ball_22_purple_139_1494', x: 139, y: 1494, color: 'purple'},
  {name: 'ball_23_green_272_1494', x: 272, y: 1494, color: 'green'},
  {name: 'ball_24_green_411_1494', x: 411, y: 1494, color: 'green'},
  {name: 'ball_25_green_684_1494', x: 684, y: 1494, color: 'green'},
  {name: 'ball_26_purple_817_1494', x: 817, y: 1494, color: 'purple'},
  {name: 'ball_27_green_956_1494', x: 956, y: 1494, color: 'green'},
];
for (var i = 0; i < balls.length; i++) {
  var b = balls[i];
  var target = b.color == "green" ? greenBalls : purpleBalls;
  var ballPath = b.color == "green" ? GREEN_BALL_PATH : PURPLE_BALL_PATH;
  placePngLayer(doc, target, BALL_SHADOW_PATH, b.name + "_shadow_from_FKJM", b.x, b.y + 53, 133, 71, 58);
  var placed = placePngLayer(doc, target, ballPath, b.name + "_source_asset_from_FKJM", b.x, b.y, 121, 121, 100);
  if (placed == null) {
    var color = b.color == "green" ? rgb(0, 205, 28) : rgb(194, 0, 225);
    fillCircleApprox(doc, target, b.name + "_fallback_shape", b.x, b.y, 59, color);
  }
}

fillRect(doc, counters, "counter_green_16_editable_placeholder", 885, 485, 121, 124, rgb(12, 180, 22));
fillRect(doc, counters, "counter_purple_11_editable_placeholder", 204, 1024, 130, 130, rgb(140, 0, 217));

addEditableText(doc, title);
placeReference(doc, guides);

doc.activeLayer = title;
alert("Production handoff scaffold created. Save as PSD after reviewing groups, editable title, reference, and object layers.");
