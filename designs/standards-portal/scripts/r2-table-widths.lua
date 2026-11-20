function Table(t)
  if t.colspecs then
    local total = 0
    for _, spec in ipairs(t.colspecs) do
      if spec[2] == 0 then spec[2] = 1 / #t.colspecs end
      total = total + spec[2]
    end
    for _, spec in ipairs(t.colspecs) do spec[2] = spec[2] / total end
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
