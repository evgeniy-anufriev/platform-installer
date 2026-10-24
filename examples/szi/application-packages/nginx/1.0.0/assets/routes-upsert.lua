local json = require "cjson.safe"
local root = "/var/lib/nginx/routes/"
local function read(path, absent)
    local file = io.open(path, "rb")
    if not file then
        if absent then return nil end
        error("APPLICATION_ROUTES_INPUT_MISSING")
    end
    local value = json.decode(file:read("*a"))
    file:close()
    assert(type(value) == "table", "APPLICATION_ROUTES_INPUT_INVALID")
    return value
end
local requested = read("/etc/nginx/routes.requested.json")
assert(type(requested.owner) == "string" and type(requested.routes) == "table", "APPLICATION_ROUTES_INPUT_INVALID")
local existing = read(root .. "routes.effective.json", true)
local effective = existing or {owner = requested.owner, routes = {}}
assert(effective.owner == requested.owner and type(effective.routes) == "table", "APPLICATION_ROUTES_OWNER_INVALID")
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local changed = not existing
for id, route in pairs(requested.routes) do
    assert(type(id) == "string" and id:match("^[a-z][a-z0-9_.-]*$") and type(route) == "table", "APPLICATION_ROUTES_INPUT_INVALID")
    assert(route.subpath == "/" .. id and type(route.endpoint) == "string" and route.endpoint:match("^https?://[^/%s]+$"), "APPLICATION_ROUTES_INPUT_INVALID")
    if not equal(effective.routes[id], route) then effective.routes[id] = route; changed = true end
end
local function atomic(path, contents)
    local file, reason = io.open(path .. ".new", "wb")
    assert(file, "APPLICATION_ROUTES_WRITE_FAILED: " .. tostring(reason))
    assert(file:write(contents)); assert(file:close())
    assert(os.rename(path .. ".new", path), "APPLICATION_ROUTES_WRITE_FAILED")
end
if changed then atomic(root .. "routes.effective.json", assert(json.encode(effective))) end
atomic(root .. "result.json", assert(json.encode({status = "ok", changed = changed})))
os.exit(0)
