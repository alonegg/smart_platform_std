function Table(t)
  if t.colspecs then
    local colspecs, total = t.colspecs, 0
    for _, spec in ipairs(colspecs) do
      if not spec[2] or spec[2] == 0 then spec[2] = 1 / #colspecs end
      total = total + spec[2]
    end
    for _, spec in ipairs(colspecs) do spec[2] = spec[2] / total end
    t.colspecs = colspecs
  else
    local widths, total = t.widths, 0
    for i, width in ipairs(widths) do
      if width == 0 then widths[i] = 1 / #widths end
      total = total + widths[i]
    end
    for i, width in ipairs(widths) do widths[i] = width / total end
    t.widths = widths
  end
  return t
end
