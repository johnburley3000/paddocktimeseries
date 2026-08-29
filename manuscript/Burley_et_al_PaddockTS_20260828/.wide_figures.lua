function Figure(fig)
  if FORMAT:match("latex") then
    return {
      pandoc.RawBlock("latex", "\\end{multicols}"),
      fig,
      pandoc.RawBlock("latex", "\\begin{multicols}{2}")
    }
  end
end
