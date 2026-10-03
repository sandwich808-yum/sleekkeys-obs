--[[
  SleekKeys for OBS  -  OBS script (Tools > Scripts > "+" > pick this file). Add it once, never touch it again.

  What it does, automatically, every time OBS starts:
    1. Starts SleekKeys if it is not already running in your tray
    2. Adds a "SleekKeys" Browser Source to your current scene (only if you don't have one yet), sized to fit your layout
  You style it in the SleekKeys editor (tray icon > Open editor); changes show up in OBS live.
  No URL to paste, no .bat to run.
]]

obs = obslua

local cfg = {
  app_path    = "",          -- optional: full path to SleekKeys.exe if it can't be found automatically
  port        = 7878,
  source_name = "SleekKeys",
  profile     = "",          -- optional: show a specific SleekKeys profile instead of the default one
  auto_add    = true,
  autostop    = false,
}

-- ------------------------------------------------------------------ helpers
local function base_url()
  return string.format("http://127.0.0.1:%d", cfg.port)
end

local function file_exists(p)
  local f = io.open(p, "rb")
  if f then f:close() return true end
  return false
end

local function url_encode(s)
  return (s:gsub("[^%w%-_%.~]", function(c) return string.format("%%%02X", string.byte(c)) end))
end

local function http_get(path)
  local h = io.popen('curl.exe -s -m 2 "' .. base_url() .. path .. '" 2>nul')
  if not h then return "" end
  local out = h:read("*a") or ""
  h:close()
  return out
end

local function is_running()
  return http_get("/api/info"):find("SleekKeys", 1, true) ~= nil
end

-- where is the app? (checked in this order)
local function find_app()
  local here = script_path():gsub("/", "\\")           -- <SleekKeys>\obs\
  local local_app = os.getenv("LOCALAPPDATA") or ""
  local candidates = {
    cfg.app_path,
    here .. "..\\SleekKeys.exe",
    here .. "..\\dist\\SleekKeys.exe",
    local_app .. "\\Programs\\SleekKeys\\SleekKeys.exe",
  }
  for _, p in ipairs(candidates) do
    if p ~= nil and p ~= "" and file_exists(p) then return p, false end
  end
  local py = here .. "..\\sleekkeys.py"                 -- running from source
  if file_exists(py) then return py, true end
  return nil, false
end

local function start_app()
  if is_running() then
    obs.script_log(obs.LOG_INFO, "SleekKeys is already running.")
    return true
  end
  local path, is_script = find_app()
  if not path then
    obs.script_log(obs.LOG_WARNING, "Could not find SleekKeys.exe. Put the path in this script's settings.")
    return false
  end
  local cmd
  if is_script then
    cmd = string.format('start "" /B pythonw "%s" --background --port %d', path, cfg.port)
  else
    cmd = string.format('start "" "%s" --background --port %d', path, cfg.port)
  end
  os.execute(cmd)
  obs.script_log(obs.LOG_INFO, "Started SleekKeys: " .. path)
  return true
end

local function stop_app()
  os.execute('curl.exe -s -m 2 -X POST -H "X-SleekKeys: 1" "' .. base_url() .. '/api/quit" >nul 2>nul')
end

local function open_editor()
  if not is_running() then start_app() end
  os.execute('curl.exe -s -m 3 -X POST -H "X-SleekKeys: 1" "' .. base_url() .. '/api/open-editor" >nul 2>nul')
end

-- the size the app says fits your layout (falls back to something reasonable)
local function wanted_size()
  local w, h = http_get("/api/info"):match('"size":%s*%[%s*(%d+)%s*,%s*(%d+)%s*%]')
  return tonumber(w) or 640, tonumber(h) or 340
end

local function overlay_url()
  local u = base_url() .. "/overlay"
  if cfg.profile ~= nil and cfg.profile ~= "" then u = u .. "?profile=" .. url_encode(cfg.profile) end
  return u
end

-- create the browser source (or refresh it) in the scene you are editing
local function ensure_source(force_update)
  local scene_source = obs.obs_frontend_get_current_scene()
  if scene_source == nil then return end
  local scene = obs.obs_scene_from_source(scene_source)
  local w, h = wanted_size()

  local s = obs.obs_data_create()
  obs.obs_data_set_string(s, "url", overlay_url())
  obs.obs_data_set_int(s, "width", w)
  obs.obs_data_set_int(s, "height", h)
  obs.obs_data_set_int(s, "fps", 60)
  obs.obs_data_set_bool(s, "shutdown", false)
  obs.obs_data_set_bool(s, "restart_when_active", false)

  local existing = obs.obs_get_source_by_name(cfg.source_name)
  if existing ~= nil then
    if force_update then
      obs.obs_source_update(existing, s)
      obs.script_log(obs.LOG_INFO, string.format("Updated '%s' (%dx%d).", cfg.source_name, w, h))
    end
    if force_update and obs.obs_scene_find_source(scene, cfg.source_name) == nil then
      obs.obs_scene_add(scene, existing)
    end
    obs.obs_source_release(existing)
  else
    local src = obs.obs_source_create("browser_source", cfg.source_name, s, nil)
    if src ~= nil then
      obs.obs_scene_add(scene, src)
      obs.obs_source_release(src)
      obs.script_log(obs.LOG_INFO, string.format("Added '%s' to your scene (%dx%d).", cfg.source_name, w, h))
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
      .. "<p>Keyboard + mouse overlay. This script starts the SleekKeys tray app and puts the overlay in your scene "
      .. "automatically - nothing to paste, nothing to launch.<br>"
      .. "Style it in the SleekKeys editor (tray icon, or the button below); changes appear in OBS live.</p>"
end

function script_properties()
  local p = obs.obs_properties_create()
  obs.obs_properties_add_bool(p, "auto_add", "Add the overlay to my scene automatically (if missing)")
  obs.obs_properties_add_text(p, "source_name", "Browser source name", obs.OBS_TEXT_DEFAULT)
  obs.obs_properties_add_text(p, "profile", "Profile to show (blank = your default)", obs.OBS_TEXT_DEFAULT)
  obs.obs_properties_add_path(p, "app_path", "SleekKeys.exe (only if not found automatically)", obs.OBS_PATH_FILE, "SleekKeys (*.exe)", nil)
  obs.obs_properties_add_int(p, "port", "Port", 1024, 65535, 1)
  obs.obs_properties_add_bool(p, "autostop", "Quit SleekKeys when OBS closes")

  obs.obs_properties_add_button(p, "btn_editor", "Open the SleekKeys editor", function() open_editor() return true end)
  obs.obs_properties_add_button(p, "btn_add", "Add / refresh overlay in current scene (match my layout size)", function() ensure_source(true) return true end)
  obs.obs_properties_add_button(p, "btn_start", "Start SleekKeys", function() start_app() return true end)
  obs.obs_properties_add_button(p, "btn_stop", "Quit SleekKeys", function() stop_app() return true end)
  return p
end

function script_defaults(settings)
  obs.obs_data_set_default_bool(settings, "auto_add", cfg.auto_add)
  obs.obs_data_set_default_string(settings, "source_name", cfg.source_name)
  obs.obs_data_set_default_string(settings, "profile", cfg.profile)
  obs.obs_data_set_default_string(settings, "app_path", cfg.app_path)
  obs.obs_data_set_default_int(settings, "port", cfg.port)
  obs.obs_data_set_default_bool(settings, "autostop", cfg.autostop)
end

function script_update(settings)
  cfg.auto_add    = obs.obs_data_get_bool(settings, "auto_add")
  cfg.source_name = obs.obs_data_get_string(settings, "source_name")
  cfg.profile     = obs.obs_data_get_string(settings, "profile")
  cfg.app_path    = obs.obs_data_get_string(settings, "app_path")
  cfg.port        = obs.obs_data_get_int(settings, "port")
  cfg.autostop    = obs.obs_data_get_bool(settings, "autostop")
end

local function first_run_setup()
  obs.timer_remove(first_run_setup)
  if cfg.auto_add then ensure_source(false) end
end

function script_load(settings)
  script_update(settings)
  start_app()
  -- give the app a moment to come up and OBS a moment to finish loading its scenes
  obs.timer_add(first_run_setup, 3000)
end

function script_unload()
  obs.timer_remove(first_run_setup)
  if cfg.autostop then stop_app() end
end
