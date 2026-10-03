--[[
  SleekKeys for OBS  -  OBS script (Tools > Scripts > "+" > pick this file)

  What it does
    * Starts / stops the SleekKeys background app (sleekkeys.py) for you
    * Adds (or updates) a "SleekKeys" Browser Source in the scene you are editing, with one click
    * Opens the SleekKeys settings page so you can pick layout, theme and colours

  Needs: Python (the same one you use to run sleekkeys.py). Lua scripting is built into OBS - no extra setup.
]]

obs = obslua

local cfg = {
  python      = "pythonw",
  port        = 7878,
  url         = "",
  source_name = "SleekKeys",
  width       = 640,
  height      = 340,
  autostart   = true,
  autostop    = true,
}

-- ------------------------------------------------------------------ helpers
local function base_url()
  return string.format("http://127.0.0.1:%d", cfg.port)
end

local function script_file()
  -- this script lives in <SleekKeys>\obs\ ; the app is one folder up
  local p = (script_path() .. "../sleekkeys.py"):gsub("/", "\\")
  return p
end

local function overlay_url()
  if cfg.url ~= nil and cfg.url:match("^https?://") then
    return cfg.url
  end
  return base_url() .. "/overlay"
end

local function is_running()
  local h = io.popen('curl.exe -s -m 1 "' .. base_url() .. '/api/info" 2>nul')
  if not h then return false end
  local out = h:read("*a") or ""
  h:close()
  return out:find("SleekKeys", 1, true) ~= nil
end

local function start_server()
  if is_running() then
    obs.script_log(obs.LOG_INFO, "SleekKeys is already running on port " .. cfg.port)
    return
  end
  local cmd = string.format('start "" /B "%s" "%s" --port %d', cfg.python, script_file(), cfg.port)
  os.execute(cmd)
  obs.script_log(obs.LOG_INFO, "Started SleekKeys: " .. cmd)
end

local function stop_server()
  os.execute('curl.exe -s -m 2 -X POST -H "X-SleekKeys: 1" "' .. base_url() .. '/api/quit" >nul 2>nul')
  obs.script_log(obs.LOG_INFO, "Asked SleekKeys to quit")
end

local function open_settings()
  os.execute('start "" "' .. base_url() .. '/"')
end

local function add_overlay()
  local scene_source = obs.obs_frontend_get_current_scene()
  if scene_source == nil then
    obs.script_log(obs.LOG_WARNING, "No scene is selected - pick a scene first.")
    return
  end
  local scene = obs.obs_scene_from_source(scene_source)

  local s = obs.obs_data_create()
  obs.obs_data_set_string(s, "url", overlay_url())
  obs.obs_data_set_int(s, "width", cfg.width)
  obs.obs_data_set_int(s, "height", cfg.height)
  obs.obs_data_set_int(s, "fps", 60)
  obs.obs_data_set_bool(s, "shutdown", false)
  obs.obs_data_set_bool(s, "restart_when_active", false)

  local existing = obs.obs_get_source_by_name(cfg.source_name)
  if existing ~= nil then
    obs.obs_source_update(existing, s)
    if obs.obs_scene_find_source(scene, cfg.source_name) == nil then
      obs.obs_scene_add(scene, existing)
    end
    obs.obs_source_release(existing)
    obs.script_log(obs.LOG_INFO, "Updated the '" .. cfg.source_name .. "' browser source.")
  else
    local src = obs.obs_source_create("browser_source", cfg.source_name, s, nil)
    if src ~= nil then
      obs.obs_scene_add(scene, src)
      obs.obs_source_release(src)
      obs.script_log(obs.LOG_INFO, "Added the '" .. cfg.source_name .. "' browser source to your scene.")
    else
      obs.script_log(obs.LOG_ERROR, "Could not create a browser source - is the OBS browser plugin installed?")
    end
  end

  obs.obs_data_release(s)
  obs.obs_source_release(scene_source)
end

-- ------------------------------------------------------------------ OBS script API
function script_description()
  return "<h2>SleekKeys</h2>"
      .. "<p>A clean keyboard + mouse overlay for streams (a NohBoard alternative).<br>"
      .. "1. <b>Start SleekKeys</b> &nbsp; 2. <b>Open settings page</b> and style it, copy its URL into the box below &nbsp; "
      .. "3. <b>Add / update overlay in current scene</b>.</p>"
end

function script_properties()
  local p = obs.obs_properties_create()
  obs.obs_properties_add_text(p, "python", "Python launcher (pythonw)", obs.OBS_TEXT_DEFAULT)
  obs.obs_properties_add_int(p, "port", "Port", 1024, 65535, 1)
  obs.obs_properties_add_text(p, "url", "Overlay URL (paste from the settings page)", obs.OBS_TEXT_DEFAULT)
  obs.obs_properties_add_text(p, "source_name", "Browser source name", obs.OBS_TEXT_DEFAULT)
  obs.obs_properties_add_int(p, "width", "Source width", 100, 4000, 10)
  obs.obs_properties_add_int(p, "height", "Source height", 100, 4000, 10)
  obs.obs_properties_add_bool(p, "autostart", "Start SleekKeys when OBS opens")
  obs.obs_properties_add_bool(p, "autostop", "Stop SleekKeys when OBS closes")

  obs.obs_properties_add_button(p, "btn_start", "Start SleekKeys", function() start_server() return true end)
  obs.obs_properties_add_button(p, "btn_stop", "Stop SleekKeys", function() stop_server() return true end)
  obs.obs_properties_add_button(p, "btn_settings", "Open settings page", function() open_settings() return true end)
  obs.obs_properties_add_button(p, "btn_add", "Add / update overlay in current scene", function() add_overlay() return true end)
  return p
end

function script_defaults(settings)
  obs.obs_data_set_default_string(settings, "python", cfg.python)
  obs.obs_data_set_default_int(settings, "port", cfg.port)
  obs.obs_data_set_default_string(settings, "url", cfg.url)
  obs.obs_data_set_default_string(settings, "source_name", cfg.source_name)
  obs.obs_data_set_default_int(settings, "width", cfg.width)
  obs.obs_data_set_default_int(settings, "height", cfg.height)
  obs.obs_data_set_default_bool(settings, "autostart", cfg.autostart)
  obs.obs_data_set_default_bool(settings, "autostop", cfg.autostop)
end

function script_update(settings)
  cfg.python      = obs.obs_data_get_string(settings, "python")
  cfg.port        = obs.obs_data_get_int(settings, "port")
  cfg.url         = obs.obs_data_get_string(settings, "url")
  cfg.source_name = obs.obs_data_get_string(settings, "source_name")
  cfg.width       = obs.obs_data_get_int(settings, "width")
  cfg.height      = obs.obs_data_get_int(settings, "height")
  cfg.autostart   = obs.obs_data_get_bool(settings, "autostart")
  cfg.autostop    = obs.obs_data_get_bool(settings, "autostop")
end

function script_load(settings)
  script_update(settings)
  if cfg.autostart then
    start_server()
  end
end

function script_unload()
  if cfg.autostop then
    stop_server()
  end
end
